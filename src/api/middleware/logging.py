"""Request logging middleware."""

import time
from typing import Callable

from fastapi import Request

from src.utils.logging import get_logger

logger = get_logger(__name__)


async def request_logging_middleware(request: Request, call_next: Callable):
    """
    Log all incoming requests with timing and response status.

    Logs:
    - Request method and path
    - Client IP
    - Response status code
    - Processing time
    """
    start_time = time.time()

    # Extract request info
    method = request.method
    path = request.url.path
    client_ip = request.client.host if request.client else None

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Log request
    log_data = {
        "method": method,
        "path": path,
        "status_code": response.status_code,
        "duration_ms": round(duration_ms, 2),
    }

    if client_ip:
        log_data["client_ip"] = client_ip

    # Log at appropriate level
    if response.status_code >= 500:
        logger.error("Request failed", **log_data)
    elif response.status_code >= 400:
        logger.warning("Request error", **log_data)
    else:
        logger.info("Request completed", **log_data)

    return response
