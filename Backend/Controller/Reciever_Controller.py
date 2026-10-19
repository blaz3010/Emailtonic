import logging
import os
from typing import Optional
from uuid import UUID

from fastapi import Depends, Form, HTTPException
from google.auth.exceptions import RefreshError
from pydantic import EmailStr, TypeAdapter, ValidationError

from Backend.DBhelper.Oauth_db import (
    disconnect_oauth_account,
    get_active_oauth_account,
)
from Backend.DBhelper.Sent_email_db import count_sent_last_24h, create_sent_email
from Backend.DBhelper.User_profiles import get_user_profile
from Backend.Middleware.auth_middleware import auth_middleware
from Backend.Utils.Crypto import decrypt
from Backend.Utils.Gmail import send_gmail_service
from Backend.Utils.Groq import generate_answer

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
DAILY_SEND_LIMIT = int(os.getenv("DAILY_SEND_LIMIT", "50"))
MAX_JD_CHARS = 10_000

_email_adapter = TypeAdapter(EmailStr)


# ----------------------------------------------------------------- helpers --
def _uid(user_id: str) -> UUID:
    try:
        return UUID(str(user_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid access token")


def _valid_email(value: Optional[str]) -> Optional[str]:
    if not value or not value.strip():
        return None
    try:
        return str(_email_adapter.validate_python(value.strip())).lower()
    except ValidationError:
        return None


def _single_line(value: str) -> str:
    """Collapse whitespace/newlines so the subject can't inject headers."""
    return " ".join((value or "").split())


def _extracted_recipient(candidate: str, job_description: str) -> Optional[str]:
    """Trust a model-extracted address only if it literally appears in the
    job description (guards against hallucination / prompt injection)."""
    email = _valid_email(candidate)
    if email and email in job_description.lower():
        return email
    return None


async def _log_email(**kwargs) -> None:
    """Best-effort history write: never fail the request because of it."""
    try:
        await create_sent_email(**kwargs)
    except Exception:
        logger.exception("Could not write sent_emails row")


# ------------------------------------------------------------------- route --
async def send_the_email(
    user_id: str = Depends(auth_middleware),
    job_description: str = Form(...),
    to: Optional[str] = Form(None),        # overrides any address found in the JD
    preview: bool = Form(False),           # True = generate only, don't send
):
    try:
        uid = _uid(user_id)

        # ---- validate input -------------------------------------------------
        jd = job_description.strip()
        if not jd:
            raise HTTPException(status_code=422, detail="Job description is required")
        if len(jd) > MAX_JD_CHARS:
            raise HTTPException(
                status_code=422,
                detail=f"Job description must be under {MAX_JD_CHARS} characters",
            )

        override = None
        if to and to.strip():
            override = _valid_email(to)
            if not override:
                raise HTTPException(status_code=422, detail="Recipient email is invalid")

        # ---- preconditions --------------------------------------------------
        profile = await get_user_profile(uid)
        if not profile or not profile.get("resume_text") or not profile.get("resume_link"):
            raise HTTPException(
                status_code=400,
                detail="Upload your resume in your profile before sending emails",
            )

        account = None
        if not preview:
            account = await get_active_oauth_account(uid, "google")
            if not account:
                raise HTTPException(status_code=409, detail="Connect your Google account first")
            if await count_sent_last_24h(uid) >= DAILY_SEND_LIMIT:
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily limit of {DAILY_SEND_LIMIT} emails reached",
                )
        try:
            draft = await generate_answer(
                resume_text=profile["resume_text"],
                job_description=jd,
                resume_drive_link=profile["resume_link"],
                github_link=profile.get("github_link"),
                leetcode_link=profile.get("leetcode_link"),
                portfolio_link=profile.get("website_link"),
            )
        except Exception:
            logger.exception("Email generation failed for user_id=%s", user_id)
            raise HTTPException(status_code=502, detail="Could not generate the email")

        subject = _single_line(draft["subject"])
        body = draft["body"]
        if not subject or not body:
            raise HTTPException(status_code=502, detail="Model returned an empty email")

        recipient = override or _extracted_recipient(draft["to"], jd)

        if preview:
            return {"status": "preview", "to": recipient, "subject": subject, "body": body}

        if not recipient:
            raise HTTPException(
                status_code=422,
                detail="No recipient found in the job description; pass the 'to' field",
            )

        # ---- send -----------------------------------------------------------
        log_base = dict(
            user_id=uid,
            oauth_account_id=account["id"],
            to_email=recipient,
            subject=subject,
            body=body,
            job_description=jd,
        )
        try:
            refresh_token = await decrypt(account["refresh_token_encrypted"])
            message_id = await send_gmail_service(
                to=recipient,
                subject=subject,
                body=body,
                refresh_token=refresh_token,
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
            )
        except RefreshError as e:
            if "invalid_grant" in str(e):  # user revoked access on Google's side
                await disconnect_oauth_account(uid, account["id"])
                raise HTTPException(status_code=401, detail="Google access was revoked; reconnect")
            logger.exception("Google token refresh failed for user_id=%s", user_id)
            await _log_email(**log_base, status="failed", error=str(e)[:500])
            raise HTTPException(status_code=502, detail="Could not refresh Google token")
        except Exception as e:
            logger.exception("Gmail send failed for user_id=%s", user_id)
            await _log_email(**log_base, status="failed", error=str(e)[:500])
            raise HTTPException(status_code=502, detail="Could not send the email")

        await _log_email(**log_base, gmail_message_id=message_id, status="sent")
        return {
            "status": "sent",
            "message": "Email sent successfully",
            "to": recipient,
            "subject": subject,
            "from": account["provider_email"],
            "gmail_message_id": message_id,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in send_the_email for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")