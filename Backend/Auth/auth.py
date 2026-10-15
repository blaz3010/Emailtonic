
import os
import secrets
import jwt

from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN_SECRET = os.environ["ACCESS_TOKEN_SECRET"]
ACCESS_TOKEN_TTL_MINUTES = int(
    os.getenv("ACCESS_TOKEN_TTL_MINUTES", "15")
)
REFRESH_TOKEN_TTL_DAYS = int(
    os.getenv("REFRESH_TOKEN_TTL_DAYS", "7")
)


async def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "user_id": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES),
    }

    return jwt.encode(
        payload,
        ACCESS_TOKEN_SECRET,
        algorithm="HS256",
    )


async def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


