import logging
import os
from typing import Optional
from uuid import UUID

from fastapi import Depends, Form, HTTPException, Query
from google.auth.exceptions import RefreshError
from pydantic import EmailStr, TypeAdapter, ValidationError

from Backend.DBhelper.Oauth_db import (
    disconnect_oauth_account,
    get_active_oauth_account,
)
from Backend.DBhelper.Sent_email_db import (
    claim_draft,
    count_sent_last_24h,
    create_draft,
    get_draft,
    list_emails,
    mark_draft_sent,
    release_draft,
)
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
MAX_REFERENCE_CHARS = 500

_email_adapter = TypeAdapter(EmailStr)


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
    return " ".join((value or "").split())


def _extracted_recipient(candidate: str, job_description: str) -> Optional[str]:
    email = _valid_email(candidate)
    if email and email in job_description.lower():
        return email
    return None


# ---------------------------------------------------------------------------
# Step 1: generate and save a draft (the only place the LLM is called)
# ---------------------------------------------------------------------------
async def create_email_draft(
    user_id: str = Depends(auth_middleware),
    job_description: str = Form(...),
    to: Optional[str] = Form(None),
    custom_reference: Optional[str] = Form(None),
):
    try:
        uid = _uid(user_id)
        jd = job_description.strip()
        if not jd:
            raise HTTPException(status_code=422, detail="Job description is required")
        if len(jd) > MAX_JD_CHARS:
            raise HTTPException(
                status_code=422,
                detail=f"Job description must be under {MAX_JD_CHARS} characters",
            )

        reference = _single_line(custom_reference or "")
        if len(reference) > MAX_REFERENCE_CHARS:
            raise HTTPException(
                status_code=422,
                detail=f"Focus note must be under {MAX_REFERENCE_CHARS} characters",
            )

        override = None
        if to and to.strip():
            override = _valid_email(to)
            if not override:
                raise HTTPException(status_code=422, detail="Recipient email is invalid")

        profile = await get_user_profile(uid)
        if not profile or not profile.get("resume_text") or not profile.get("resume_link"):
            raise HTTPException(
                status_code=400,
                detail="Add your resume and resume link in your profile before generating emails",
            )

        try:
            draft = await generate_answer(
                resume_text=profile["resume_text"],
                custom_reference=reference or None,
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
        row = await create_draft(uid, recipient, subject, body, jd)

        return {
            "id": str(row["id"]),
            "status": "draft",
            "to": recipient,
            "subject": subject,
            "body": body,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in create_email_draft for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")


# ---------------------------------------------------------------------------
# Step 2: approve and send the stored draft (no LLM call)
# ---------------------------------------------------------------------------
async def send_email_draft(
    draft_id: UUID,
    user_id: str = Depends(auth_middleware),
    to: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    body: Optional[str] = Form(None),
):
    try:
        uid = _uid(user_id)

        row = await get_draft(uid, draft_id)
        if not row:
            raise HTTPException(status_code=404, detail="Draft not found")
        if row["status"] != "draft":
            raise HTTPException(status_code=409, detail=f"Email is already {row['status']}")

        recipient = row["to_email"]
        if to and to.strip():
            recipient = _valid_email(to)
            if not recipient:
                raise HTTPException(status_code=422, detail="Recipient email is invalid")
        if not recipient:
            raise HTTPException(status_code=422, detail="No recipient found; pass the 'to' field")

        final_subject = _single_line(subject) if subject and subject.strip() else row["subject"]
        final_body = body.strip() if body and body.strip() else row["body"]

        account = await get_active_oauth_account(uid, "google")
        if not account:
            raise HTTPException(status_code=409, detail="Connect your Google account first")
        if await count_sent_last_24h(uid) >= DAILY_SEND_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"Daily limit of {DAILY_SEND_LIMIT} emails reached",
            )

        # Atomic draft -> sending, so a double-click can't send twice
        claimed = await claim_draft(uid, draft_id, account["id"], recipient, final_subject, final_body)
        if not claimed:
            raise HTTPException(status_code=409, detail="This email is already being sent")

        try:
            refresh_token = await decrypt(account["refresh_token_encrypted"])
            message_id = await send_gmail_service(
                to=recipient,
                subject=final_subject,
                body=final_body,
                refresh_token=refresh_token,
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
            )
        except RefreshError as e:
            if "invalid_grant" in str(e):
                await disconnect_oauth_account(uid, account["id"])
                await release_draft(draft_id, "Google access revoked")
                raise HTTPException(status_code=401, detail="Google access was revoked; reconnect")
            logger.exception("Google token refresh failed for user_id=%s", user_id)
            await release_draft(draft_id, str(e))
            raise HTTPException(status_code=502, detail="Could not refresh Google token")
        except Exception as e:
            logger.exception("Gmail send failed for user_id=%s", user_id)
            await release_draft(draft_id, str(e))
            raise HTTPException(status_code=502, detail="Could not send the email")

        await mark_draft_sent(draft_id, message_id)
        return {
            "id": str(draft_id),
            "status": "sent",
            "to": recipient,
            "subject": final_subject,
            "body": final_body,
            "from": account["provider_email"],
            "gmail_message_id": message_id,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in send_email_draft for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")


# ---------------------------------------------------------------------------
# The "log table" view
# ---------------------------------------------------------------------------
async def email_history(
    user_id: str = Depends(auth_middleware),
    status: Optional[str] = Query(None, pattern="^(draft|sending|sent|failed)$"),
    limit: int = Query(50, ge=1, le=200),
):
    try:
        uid = _uid(user_id)
        emails = await list_emails(uid, status, limit)
        return {"emails": emails}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in email_history for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")