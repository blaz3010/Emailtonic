
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import text

from Backend.DBhelper.db import AsyncDB

load_dotenv()


async def create_user(
    username: str,
    email: str,
    password_hash: str,
    refresh_token: Optional[str] = None,
    expiry_at: Optional[datetime] = None,
) -> Optional[dict]:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                INSERT INTO users (
                    username,
                    email,
                    password_hash,
                    refresh_token,
                    expiry_at
                )
                VALUES (
                    :username,
                    :email,
                    :password_hash,
                    :refresh_token,
                    :expiry_at
                )
                ON CONFLICT (email) DO NOTHING
                RETURNING id, username, email, created_at
            """),
            {
                "username": username,
                "email": email,
                "password_hash": password_hash,
                "refresh_token": refresh_token,
                "expiry_at": expiry_at,
            },
        )
        await s.commit()
        row = result.mappings().first()
        return dict(row) if row else None


async def get_user_by_id(user_id: UUID) -> Optional[dict]:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                SELECT *
                FROM users
                WHERE id = :id
            """),
            {"id": str(user_id)},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def get_user_by_email(email: str) -> Optional[dict]:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                SELECT *
                FROM users
                WHERE email = :email
            """),
            {"email": email},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def update_user_password(
    user_id: UUID,
    password_hash: str,
) -> int:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                UPDATE users
                SET password_hash = :password_hash,
                    updated_at = NOW()
                WHERE id = :id
            """),
            {
                "id": str(user_id),
                "password_hash": password_hash,
            },
        )
        await s.commit()
        return result.rowcount


async def update_gmail_refresh_token(
    user_id: UUID,
    encrypted_refresh_token: str,
) -> int:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                UPDATE users
                SET refresh_token = :refresh_token,
                    updated_at = NOW()
                WHERE id = :id
            """),
            {
                "id": str(user_id),
                "refresh_token": encrypted_refresh_token,
            },
        )
        await s.commit()
        return result.rowcount


async def update_gmail_token_expiry(
    user_id: UUID,
    expiry_at: datetime,
) -> int:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                UPDATE users
                SET expiry_at = :expiry_at,
                    updated_at = NOW()
                WHERE id = :id
            """),
            {
                "id": str(user_id),
                "expiry_at": expiry_at,
            },
        )
        await s.commit()
        return result.rowcount


async def update_gmail_credentials(
    user_id: UUID,
    encrypted_refresh_token: str,
    expiry_at: Optional[datetime] = None,
) -> int:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                UPDATE users
                SET refresh_token = :refresh_token,
                    expiry_at = :expiry_at,
                    updated_at = NOW()
                WHERE id = :id
            """),
            {
                "id": str(user_id),
                "refresh_token": encrypted_refresh_token,
                "expiry_at": expiry_at,
            },
        )
        await s.commit()
        return result.rowcount


async def delete_user(user_id: UUID) -> int:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                DELETE FROM users
                WHERE id = :id
            """),
            {"id": str(user_id)},
        )
        await s.commit()
        return result.rowcount
