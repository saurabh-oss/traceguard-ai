from fastapi import Header, HTTPException, status
from app.config import settings


async def require_api_key(x_api_key: str = Header(default="")):
    """Dependency: enforce X-API-Key when TRACEGUARD_API_KEY is configured."""
    if not settings.api_key:
        return  # auth disabled — open for local dev / demos
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or missing X-API-Key header")
