"""Authentication middleware for API key validation."""

from typing import Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.config.settings import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def api_key_middleware(request: Request, call_next: Callable):
    """
    Validate API key for protected endpoints.

    Requires X-API-Key header matching configured admin API key.
    Skips validation for health check endpoints.
    """
    # Skip auth for health checks and docs
    if request.url.path in ["/health", "/health/detailed", "/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)

    # Skip auth for non-API endpoints
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    # Check for API key header
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        logger.warning(
            "Missing API key",
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing API key. Provide X-API-Key header."},
        )

    # Validate API key
    expected_key = settings.admin.api_key.get_secret_value()
    if api_key != expected_key:
        logger.warning(
            "Invalid API key",
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Invalid API key"},
        )

    # API key valid, continue
    return await call_next(request)
