import io
import os
import logging
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import (
    Body,
    Cookie,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError

from Backend.Auth.auth import (
    REFRESH_TOKEN_TTL_DAYS,
    create_access_token,
    create_refresh_token
)
from Backend.DBhelper.User_db import (
    clear_session_refresh,
    create_user,
    delete_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_session_hash,
    get_user_by_username,
    set_session_refresh,
    update_user_password,
)
from Backend.DBhelper.User_profiles import (
    create_user_profile,
    delete_user_profile,
    get_user_profile,
    update_user_profile,
)
from Backend.Middleware.auth_middleware import auth_middleware
from Backend.Utils.Cloudinary import upload_resume
from Backend.Utils.Hash import hash_password, verify_password
from Backend.Utils.PdfReader import read_text_from_pdf

logger = logging.getLogger(__name__)

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "strict").lower()
MAX_RESUME_BYTES = 5 * 1024 * 1024


# ----------------------------------------------------------------- helpers --
def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )


async def _issue_tokens(response: Response, user_id: str) -> str:
    """Create access + refresh tokens, store the refresh hash, set the cookie.
    Returns the access token (sent to the client in the JSON body)."""
    access_token = await create_access_token(user_id)
    refresh_token = await create_refresh_token()

    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    stored = await set_session_refresh(
        UUID(user_id), await hash_refresh_token(refresh_token), expires_at
    )
    if not stored:
        raise HTTPException(status_code=500, detail="Could not persist refresh token")

    _set_refresh_cookie(response, refresh_token)
    return access_token

async def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _public_user(user: dict) -> dict:
    """Allow-list: never leak password hash or token columns."""
    return {
        "id": str(user["id"]),
        "username": user["username"],
        "email": user["email"],
        "created_at": user.get("created_at"),
    }


def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    if len(password.encode()) > 72:  # bcrypt ignores everything past 72 bytes
        raise HTTPException(status_code=422, detail="Password must be at most 72 bytes")


def _uid(user_id: str) -> UUID:
    try:
        return UUID(str(user_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid access token")


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


# --------------------------------------------------------------- auth routes --
async def create_user_new(
    response: Response,
    username: str = Body(...),
    email: EmailStr = Body(...),
    password: str = Body(...),
):
    try:
        username = username.strip()
        email = email.lower()

        if len(username) < 3 or len(username) > 50:
            raise HTTPException(status_code=422, detail="Username must be 3-50 characters")
        _validate_password(password)

        if await get_user_by_email(email):
            raise HTTPException(status_code=400, detail="User with this email already exists")
        if await get_user_by_username(username):
            raise HTTPException(status_code=400, detail="Username already taken")

        hashed_password = await hash_password(password)
        try:
            created = await create_user(
                username=username, email=email, password_hash=hashed_password
            )
        except IntegrityError:
            created = None
        if not created:
            raise HTTPException(
                status_code=400,
                detail="Could not create user (username or email conflict)",
            )

        user_id = str(created["id"])
        access_token = await _issue_tokens(response, user_id)

        return {
            "message": "User created successfully",
            "user_id": user_id,
            "username": username,
            "email": email,
            "access_token": access_token,
            "token_type": "bearer",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in create_user_new")
        raise HTTPException(status_code=500, detail="An internal error occurred during signup")


async def login_user(
    response: Response,
    username: str = Body(...),  # username or email
    password: str = Body(...),
):
    try:
        logger.info("Login attempt received")

        username = username.strip()
        user = await get_user_by_username(username)
        if not user and "@" in username:
            user = await get_user_by_email(username.lower())

        # always run a bcrypt check so timing doesn't reveal whether the user exists
        password_valid = await verify_password(password, user["password_hash"]) if user else False
        if not user or not password_valid:
            logger.warning("Login failed")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_id = str(user["id"])
        access_token = await _issue_tokens(response, user_id)

        return {
            "message": "Login successful",
            "user_id": user_id,
            "username": user.get("username"),
            "access_token": access_token,
            "token_type": "bearer",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during login")
        raise HTTPException(status_code=500, detail="An internal error occurred during login")


async def refresh_access_token(
    response: Response,
    refresh_token: str = Cookie(None),
):
    try:
        if not refresh_token:
            raise HTTPException(status_code=401, detail="No refresh token provided")

        user = await get_user_by_session_hash(await hash_refresh_token(refresh_token))
        expires_at = user.get("session_expires_at") if user else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if not user or not expires_at or expires_at <= datetime.now(timezone.utc):
            response.delete_cookie("refresh_token", path="/")
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

        new_access_token = await _issue_tokens(response, str(user["id"]))
        return {"access_token": new_access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in refresh_access_token")
        raise HTTPException(status_code=500, detail="An internal error occurred")


async def logout_user(
    response: Response,
    refresh_token: str = Cookie(None),
):
    try:
        if refresh_token:
            user = await get_user_by_session_hash(await hash_refresh_token(refresh_token))
            if user:
                await clear_session_refresh(user["id"])
        response.delete_cookie("refresh_token", path="/")
        return {"message": "Logged out successfully"}
    except Exception:
        logger.exception("Unexpected error in logout_user")
        raise HTTPException(status_code=500, detail="An internal error occurred")



async def get_me(user_id: str = Depends(auth_middleware)):
    try:
        uid = _uid(user_id)
        user = await get_user_by_id(uid)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        profile = await get_user_profile(uid)
        return {"user": _public_user(user), "profile": profile}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in get_me for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")


async def change_password(
    response: Response,
    old_password: str = Body(...),
    new_password: str = Body(...),
    user_id: str = Depends(auth_middleware),
):
    try:
        uid = _uid(user_id)
        user = await get_user_by_id(uid)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not await verify_password(old_password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Old password is incorrect")
        _validate_password(new_password)
        if old_password == new_password:
            raise HTTPException(status_code=400, detail="New password must be different")

        await update_user_password(uid, await hash_password(new_password))
        # revoke the refresh token: every device has to log in again
        await clear_session_refresh(uid)
        response.delete_cookie("refresh_token", path="/")
        return {"message": "Password updated. Please log in again."}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in change_password for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")


async def delete_account(
    response: Response,
    password: str = Body(..., embed=True),
    user_id: str = Depends(auth_middleware),
):
    try:
        uid = _uid(user_id)
        user = await get_user_by_id(uid)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not await verify_password(password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Password is incorrect")

        await delete_user_profile(uid)  # harmless if none exists / FK cascades
        await delete_user(uid)
        response.delete_cookie("refresh_token", path="/")
        return {"message": "Account deleted"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in delete_account for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")


async def _read_resume(resume: UploadFile) -> tuple[bytes, str]:
    if resume.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=415, detail="Resume must be a PDF")

    data = await resume.read(MAX_RESUME_BYTES + 1)
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="Resume must be under 5 MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="File is not a valid PDF")

    try:
        text = await read_text_from_pdf(data, resume.filename or "resume.pdf")
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read the PDF")
    if not text:
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted from the PDF",
        )
    return data, text




async def get_profile(user_id: str = Depends(auth_middleware)):
    try:
        profile = await get_user_profile(_uid(user_id))
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return profile
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in get_profile for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")


async def create_profile(
    user_id: str = Depends(auth_middleware),
    resume: Optional[UploadFile] = File(None),
    leetcode_link: Optional[str] = Form(None),
    github_link: Optional[str] = Form(None),
    website_link: Optional[str] = Form(None),
    resume_link: Optional[str] = Form(None),
):
    try:
        uid = _uid(user_id)
        if await get_user_profile(uid):
            raise HTTPException(status_code=409, detail="Profile already exists; use PUT")

        resume_text = None  # don't clobber the resume_link form value
        if resume is not None and resume.filename:
            data, resume_text = await _read_resume(resume)

        try:
            profile = await create_user_profile(
                user_id=uid,
                resume_link=_clean(resume_link),
                resume_text=resume_text,
                leetcode_link=_clean(leetcode_link),
                github_link=_clean(github_link),
                website_link=_clean(website_link),
            )
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Profile already exists; use PUT")
        return {"message": "Profile created", "profile": profile}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in create_profile for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")


async def update_profile(
    user_id: str = Depends(auth_middleware),
    resume: Optional[UploadFile] = File(None),
    leetcode_link: Optional[str] = Form(None),
    github_link: Optional[str] = Form(None),
    website_link: Optional[str] = Form(None),
    resume_link: Optional[str] = Form(None),
):
    try:
        uid = _uid(user_id)
        if not await get_user_profile(uid):
            raise HTTPException(status_code=404, detail="Profile not found; use POST")

        fields = {
            "resume_link": _clean(resume_link),   # added
            "leetcode_link": _clean(leetcode_link),
            "github_link": _clean(github_link),
            "website_link": _clean(website_link),
        }
        if resume is not None and resume.filename:
            data, fields["resume_text"] = await _read_resume(resume)

        if not any(v is not None for v in fields.values()):
            raise HTTPException(status_code=400, detail="Nothing to update")

        await update_user_profile(uid, **fields)
        return {"message": "Profile updated", "profile": await get_user_profile(uid)}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in update_profile for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="An internal error occurred")