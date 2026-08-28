import secrets

from fastapi import Header, HTTPException, status

from app.config import settings


def verify_api_key(token: str | None) -> bool:
    """Constant-time comparison of a caller-supplied token against the configured key."""
    if not token:
        return False
    return secrets.compare_digest(token, settings.api_key)


async def require_api_key(x_api_key: str | None = Header(None, alias="Authorization")) -> str:
    if not x_api_key or not x_api_key.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if not verify_api_key(x_api_key.removeprefix("Bearer ")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return "user"
