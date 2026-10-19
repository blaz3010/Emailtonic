import os

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()

ACCESS_TOKEN_SECRET = os.environ["ACCESS_TOKEN_SECRET"]

# auto_error=False so we can return our own 401 message.
# This also adds the "Authorize" button to Swagger (/docs) for testing.
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Access token has expired")
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid access token")

    if payload.get("type") != "access" or not payload.get("user_id"):
        raise _unauthorized("Invalid access token")
    return payload


async def auth_middleware(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Reads `Authorization: Bearer <access_token>` and returns the user_id."""
    if creds is None or not creds.credentials:
        raise _unauthorized("Access token is missing")
    payload = await verify_access_token(creds.credentials)
    return payload["user_id"]