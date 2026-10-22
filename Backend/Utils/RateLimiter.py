from fastapi import Request
from slowapi.util import get_remote_address
async def get_rate_limit_key(request: Request) -> str:
    user_id = request.headers.get("user_id")
    if user_id is None:
        return get_remote_address(request)
    return user_id
