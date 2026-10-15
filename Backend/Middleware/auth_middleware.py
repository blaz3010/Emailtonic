import os
import secrets
import jwt
from fastapi import Cookie,HTTPException
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

async def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            os.environ["ACCESS_TOKEN_SECRET"],
            algorithms=["HS256"],
        )
        if payload.get("type") != "access":
            raise jwt.InvalidTokenError("Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("Access token has expired")
    except jwt.InvalidTokenError as e:
        raise Exception(f"Invalid access token: {str(e)}")

async def auth_middleware(access_token:str=Cookie(None)):
    if not access_token:
        raise HTTPException(status_code=401, detail="Access token is missing")
    try:
        payload = await verify_access_token(access_token)
        return payload["user_id"]
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))