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
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                SELECT count(*) AS n
                FROM sent_emails
                WHERE user_id = :user_id
                  AND status = 'sent'
                  AND created_at >= NOW() - INTERVAL '24 hours'
            """),
            {"user_id": str(user_id)},
        )
        return int(result.scalar_one())