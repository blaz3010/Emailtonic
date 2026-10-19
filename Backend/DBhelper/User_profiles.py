
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from Backend.DBhelper.db import     AsyncDB


async def create_user_profile(
    user_id: UUID,
    resume_link: Optional[str] = None,
    resume_text: Optional[str] = None,
    leetcode_link: Optional[str] = None,
    github_link: Optional[str] = None,
    website_link: Optional[str] = None,
) -> Optional[dict]:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                INSERT INTO user_profiles (
                    user_id,
                    resume_link,
                    resume_text,
                    leetcode_link,
                    github_link,
                    website_link
                )
                VALUES (
                    :user_id,
                    :resume_link,
                    :resume_text,
                    :leetcode_link,
                    :github_link,
                    :website_link
                )
                RETURNING *
            """),
            {
                "user_id": str(user_id),
                "resume_link": resume_link,
                "resume_text": resume_text,
                "leetcode_link": leetcode_link,
                "github_link": github_link,
                "website_link": website_link,
            },
        )
        await s.commit()
        row = result.mappings().first()
        return dict(row) if row else None


async def get_user_profile(user_id: UUID) -> Optional[dict]:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                SELECT *
                FROM user_profiles
                WHERE user_id = :user_id
            """),
            {"user_id": str(user_id)},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def update_user_profile(
    user_id: UUID,
    resume_link: Optional[str] = None,
    resume_text: Optional[str] = None,
    leetcode_link: Optional[str] = None,
    github_link: Optional[str] = None,
    website_link: Optional[str] = None,
) -> int:
    updates = {
        "resume_link": resume_link,
        "resume_text": resume_text,
        "leetcode_link": leetcode_link,
        "github_link": github_link,
        "website_link": website_link,
    }

    updates = {
        key: value
        for key, value in updates.items()
        if value is not None
    }

    if not updates:
        return 0

    set_clause = ", ".join(
        f"{column} = :{column}" for column in updates
    )

    query = text(f"""
        UPDATE user_profiles
        SET {set_clause}, updated_at = NOW()
        WHERE user_id = :user_id
    """)

    async with AsyncDB() as s:
        result = await s.execute(
            query,
            {**updates, "user_id": str(user_id)},
        )
        await s.commit()
        return result.rowcount


async def delete_user_profile(user_id: UUID) -> int:
    async with AsyncDB() as s:
        result = await s.execute(
            text("""
                DELETE FROM user_profiles
                WHERE user_id = :user_id
            """),
            {"user_id": str(user_id)},
        )
        await s.commit()
        return result.rowcount
