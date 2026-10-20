from typing import Optional
from uuid import UUID

from sqlalchemy import text

from Backend.DBhelper.db import AsyncDB


async def create_sent_email(
    user_id: UUID,
    to_email: str,
    subject: str,
    body: str,
    job_description: Optional[str] = None,
    oauth_account_id: Optional[UUID] = None,
    gmail_message_id: Optional[str] = None,
    status: str = "sent",
    error: Optional[str] = None,
) -> Optional[dict]:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                INSERT INTO sent_emails (
                    user_id,
                    oauth_account_id,
                    to_email,
                    subject,
                    body,
                    job_description,
                    gmail_message_id,
                    status,
                    error
                )
                VALUES (
                    :user_id,
                    :oauth_account_id,
                    :to_email,
                    :subject,
                    :body,
                    :job_description,
                    :gmail_message_id,
                    :status,
                    :error
                )
                RETURNING id, to_email, subject, status, created_at
            """),
            {
                "user_id": str(user_id),
                "oauth_account_id": str(oauth_account_id) if oauth_account_id else None,
                "to_email": to_email,
                "subject": subject,
                "body": body,
                "job_description": job_description,
                "gmail_message_id": gmail_message_id,
                "status": status,
                "error": error,
            },
        )
        await s.commit()
        row = result.mappings().first()
        return dict(row) if row else None


async def count_sent_last_24h(user_id: UUID) -> int:
    # Drafts don't count toward the daily limit; in-flight sends do.
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                SELECT count(*) AS n
                FROM sent_emails
                WHERE user_id = :user_id
                  AND status IN ('sent', 'sending')
                  AND COALESCE(sent_at, created_at) >= NOW() - INTERVAL '24 hours'
            """),
            {"user_id": str(user_id)},
        )
        return int(result.scalar_one())


# ---------------------------------------------------------------------------
# Draft workflow
# ---------------------------------------------------------------------------

async def create_draft(
    user_id: UUID,
    to_email: Optional[str],
    subject: str,
    body: str,
    job_description: Optional[str],
) -> dict:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                INSERT INTO sent_emails (user_id, to_email, subject, body, job_description, status)
                VALUES (:user_id, :to_email, :subject, :body, :jd, 'draft')
                RETURNING *
            """),
            {
                "user_id": str(user_id),
                "to_email": to_email,
                "subject": subject,
                "body": body,
                "jd": job_description,
            },
        )
        await s.commit()
        return dict(result.mappings().first())


async def get_draft(user_id: UUID, draft_id: UUID) -> Optional[dict]:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                SELECT *
                FROM sent_emails
                WHERE id = :id AND user_id = :user_id
            """),
            {"id": str(draft_id), "user_id": str(user_id)},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def claim_draft(
    user_id: UUID,
    draft_id: UUID,
    account_id: UUID,
    to_email: str,
    subject: str,
    body: str,
) -> Optional[dict]:
    """Atomically move draft -> sending. Returns None if it was already claimed."""
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                UPDATE sent_emails
                SET status = 'sending',
                    oauth_account_id = :account_id,
                    to_email = :to_email,
                    subject = :subject,
                    body = :body,
                    error = NULL
                WHERE id = :id AND user_id = :user_id AND status = 'draft'
                RETURNING *
            """),
            {
                "id": str(draft_id),
                "user_id": str(user_id),
                "account_id": str(account_id),
                "to_email": to_email,
                "subject": subject,
                "body": body,
            },
        )
        await s.commit()
        row = result.mappings().first()
        return dict(row) if row else None


async def mark_draft_sent(draft_id: UUID, gmail_message_id: str) -> None:
    async with AsyncDB() as s:
        await s.execute(
            text("""
                UPDATE sent_emails
                SET status = 'sent', gmail_message_id = :mid, sent_at = NOW(), error = NULL
                WHERE id = :id
            """),
            {"id": str(draft_id), "mid": gmail_message_id},
        )
        await s.commit()


async def release_draft(draft_id: UUID, error: str) -> None:
    """Send failed: put it back to 'draft' so the user can retry without regenerating."""
    async with AsyncDB() as s:
        await s.execute(
            text("""
                UPDATE sent_emails
                SET status = 'draft', error = :error
                WHERE id = :id
            """),
            {"id": str(draft_id), "error": (error or "")[:500]},
        )
        await s.commit()


async def list_emails(
    user_id: UUID,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                SELECT id, to_email, subject, body, status, error, created_at, sent_at
                FROM sent_emails
                WHERE user_id = :user_id
                  AND (CAST(:status AS text) IS NULL OR status = CAST(:status AS text))
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"user_id": str(user_id), "status": status, "limit": limit},
        )
        return [dict(r) for r in result.mappings().all()]