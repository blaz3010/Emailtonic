import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Verified against when the user doesn't exist, so a login attempt takes
# about the same time whether or not the account is real.
DUMMY_HASH = password_hasher.hash("not-a-real-password")


async def hash_password(password: str) -> str:
    # Argon2 is deliberately slow and memory-heavy, so run it in a worker
    # thread instead of blocking FastAPI's event loop.
    return await asyncio.to_thread(password_hasher.hash, password)


async def verify_password(password: str, stored_hash: str) -> bool:
    def _verify() -> bool:
        try:
            return password_hasher.verify(stored_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    return await asyncio.to_thread(_verify)