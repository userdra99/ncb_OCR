"""Rate limiting middleware using slowapi."""

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    Limiter = None
    get_remote_address = None
    RateLimitExceeded = None
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Initialize limiter (only if slowapi is available)
if SLOWAPI_AVAILABLE:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200/minute", "5000/hour"],  # Global rate limits
        storage_uri="memory://",  # Use in-memory storage (can be changed to Redis for distributed)
    )
else:
    limiter = None


def optional_limit(limit_string: str):
    """
    Decorator that applies rate limiting only if slowapi is available.

    If slowapi is not installed, this decorator becomes a no-op,
    allowing the endpoint to function without rate limiting.

    Args:
        limit_string: Rate limit specification (e.g., "10/minute")

    Returns:
        Decorated function with rate limiting if slowapi is available,
        otherwise the original function unchanged.
    """
    def decorator(func):
        if SLOWAPI_AVAILABLE and limiter:
            return limiter.limit(limit_string)(func)
        return func
    return decorator


async def rate_limit_error_handler(request: Request, exc) -> JSONResponse:
    """
    Custom error handler for rate limit exceeded.

    Returns:
        JSONResponse with 429 status code and helpful error message
    """
    if not SLOWAPI_AVAILABLE:
        return JSONResponse(
            status_code=500,
            content={"error": "Rate limiting not available (slowapi not installed)"}
        )

    logger.warning(
        "Rate limit exceeded",
        ip=get_remote_address(request) if get_remote_address else "unknown",
        path=request.url.path,
        limit=str(getattr(exc, 'detail', 'unknown'))
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please slow down.",
            "detail": str(getattr(exc, 'detail', 'unknown')),
        },
        headers={"Retry-After": str(60)}  # Suggest retry after 60 seconds
    )


# Specific rate limits for different endpoint types
RATE_LIMITS = {
    # Public endpoints - stricter limits
    "health": "60/minute",

    # Stats endpoints - moderate limits (for dashboards)
    "stats_summary": "30/minute",
    "stats_jobs": "100/minute",  # Pagination endpoint can handle more
    "stats_daily": "20/minute",
    "stats_dashboard": "10/minute",  # Deprecated endpoint with high memory usage

    # Job management - moderate limits
    "job_create": "100/minute",
    "job_get": "200/minute",
    "job_list": "50/minute",

    # Exception handling - stricter limits (manual review)
    "exception_get": "50/minute",
    "exception_list": "20/minute",
}
