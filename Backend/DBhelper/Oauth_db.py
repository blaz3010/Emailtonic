
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
import hashlib
import secrets

from sqlalchemy import text

from Backend.DBhelper.db import AsyncDB


# =========================================================
# OAUTH ACCOUNTS
# =========================================================

async def save_oauth_account(
    user_id: UUID,
    provider_email: str,
    encrypted_refresh_token: Optional[str],
    scopes: str,
    provider: str = "google",
) -> Optional[dict]:
    """
    Insert a Gmail connection or update an existing one.

    If encrypted_refresh_token is None, preserve the existing
    refresh token. A new account requires a refresh token.
    """

    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                INSERT INTO oauth_accounts (
                    user_id,
                    provider,
                    provider_email,
                    refresh_token_encrypted,
                    scopes
                )
                VALUES (
                    :user_id,
                    :provider,
                    :provider_email,
                    :refresh_token_encrypted,
                    :scopes
                )
                ON CONFLICT (
                    user_id,
                    provider,
                    provider_email
                )
                DO UPDATE SET
                    refresh_token_encrypted = CASE
                        WHEN :new_token IS NOT NULL
                        THEN EXCLUDED.refresh_token_encrypted
                        ELSE oauth_accounts.refresh_token_encrypted
                    END,
                    scopes = EXCLUDED.scopes,
                    revoked_at = NULL,
                    updated_at = NOW()
                RETURNING
                    id,
                    user_id,
                    provider,
                    provider_email,
                    scopes,
                    created_at,
                    updated_at
            """),
            {
                "user_id": str(user_id),
                "provider": provider,
                "provider_email": provider_email.strip().lower(),
                "refresh_token_encrypted": encrypted_refresh_token,
                "new_token": encrypted_refresh_token,
                "scopes": scopes,
            },
        )

        await s.commit()
        row = result.mappings().first()
        return dict(row) if row else None


async def get_oauth_account_by_id(
    user_id: UUID,
    account_id: UUID,
) -> Optional[dict]:
    """Fetch an OAuth account owned by a specific user."""

    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                SELECT
                    id,
                    user_id,
                    provider,
                    provider_email,
                    refresh_token_encrypted,
                    scopes,
                    revoked_at,
                    created_at,
                    updated_at
                FROM oauth_accounts
                WHERE id = :account_id
                  AND user_id = :user_id
            """),
            {
                "account_id": str(account_id),
                "user_id": str(user_id),
            },
        )

        row = result.mappings().first()
        return dict(row) if row else None


async def get_active_oauth_account(
    user_id: UUID,
    provider: str = "google",
) -> Optional[dict]:
    """Fetch one active OAuth account for sending emails."""

    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                SELECT
                    id,
                    user_id,
                    provider,
                    provider_email,
                    refresh_token_encrypted,
                    scopes,
                    created_at,
                    updated_at
                FROM oauth_accounts
                WHERE user_id = :user_id
                  AND provider = :provider
                  AND revoked_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {
                "user_id": str(user_id),
                "provider": provider,
            },
        )

        row = result.mappings().first()
        return dict(row) if row else None


async def get_user_oauth_accounts(
    user_id: UUID,
    provider: str = "google",
) -> list[dict]:
    """List connected accounts without returning credentials."""

    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                SELECT
                    id,
                    provider,
                    provider_email,
                    scopes,
                    created_at,
                    updated_at
                FROM oauth_accounts
                WHERE user_id = :user_id
                  AND provider = :provider
                  AND revoked_at IS NULL
                ORDER BY created_at DESC
            """),
            {
                "user_id": str(user_id),
                "provider": provider,
            },
        )

        return [dict(row) for row in result.mappings().all()]


async def disconnect_oauth_account(
    user_id: UUID,
    account_id: UUID,
) -> int:
    """Disable an account and remove its stored refresh token."""

    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                UPDATE oauth_accounts
                SET revoked_at = NOW(),
                    refresh_token_encrypted = '',
                    updated_at = NOW()
                WHERE id = :account_id
                  AND user_id = :user_id
                  AND revoked_at IS NULL
            """),
            {
                "account_id": str(account_id),
                "user_id": str(user_id),
            },
        )

        await s.commit()
        return result.rowcount


# =========================================================
# OAUTH STATES
# =========================================================

def hash_oauth_state(state: str) -> str:
    """Hash raw OAuth state using SHA-256."""

    return hashlib.sha256(state.encode("utf-8")).hexdigest()


async def create_oauth_state(
    user_id: UUID,
    ttl_minutes: int = 10,
) -> str:
    """
    Create a random OAuth state.

    Only the hash is stored in the database.
    The raw state is returned for Google's authorization URL.
    """

    raw_state = secrets.token_urlsafe(32)
    state_hash = hash_oauth_state(raw_state)

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ttl_minutes
    )

    async with AsyncDB() as s:
        await s.execute(
            text("""
                INSERT INTO oauth_states (
                    state_hash,
                    user_id,
                    expires_at
                )
                VALUES (
                    :state_hash,
                    :user_id,
                    :expires_at
                )
            """),
            {
                "state_hash": state_hash,
                "user_id": str(user_id),
                "expires_at": expires_at,
            },
        )

        await s.commit()

    return raw_state


async def consume_oauth_state(
    raw_state: str,
) -> Optional[UUID]:
    """
    Atomically validate and consume a state.

    Returns user_id only if the state exists, has not expired,
    and has never been consumed. Returns None otherwise.
    """

    state_hash = hash_oauth_state(raw_state)
    now = datetime.now(timezone.utc)

    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                UPDATE oauth_states
                SET used_at = :now
                WHERE state_hash = :state_hash
                  AND expires_at > :now
                  AND used_at IS NULL
                RETURNING user_id
            """),
            {
                "state_hash": state_hash,
                "now": now,
            },
        )

        row = result.mappings().first()
        await s.commit()

        return UUID(str(row["user_id"])) if row else None


async def delete_expired_oauth_states() -> int:
    """Clean up expired or already-consumed OAuth states."""

    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                DELETE FROM oauth_states
                WHERE expires_at <= NOW()
                   OR used_at IS NOT NULL
            """)
        )

        await s.commit()
        return result.rowcount
