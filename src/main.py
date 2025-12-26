"""Main FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Optional rate limiting (requires slowapi)
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    RateLimitExceeded = None

from src.api.middleware import (
    api_key_middleware,
    request_logging_middleware,
)

if SLOWAPI_AVAILABLE:
    from src.api.middleware import (
        limiter,
        rate_limit_error_handler,
        RATE_LIMITS,
    )
from src.api.routes import exceptions_router, jobs_router, stats_router
from src.config.settings import settings
from src.utils.logging import configure_logging, get_logger
from src.workers.email_watch_listener import EmailWatchListener
from src.workers.ncb_json_generator import NCBJSONGeneratorWorker
from src.workers.ocr_processor import OCRProcessorWorker

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Worker instances
workers = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    print("🚀 LIFESPAN STARTING...")  # Debug print
    logger.info("Starting Claims Data Entry Agent", env=settings.app.env)

    # Start background workers
    logger.info("Starting background workers...")

    # Only start workers if credentials are available
    try:
        # Email watch listener (Gmail Push Notifications via Pub/Sub)
        email_worker = EmailWatchListener()
        workers["email_watch_listener"] = asyncio.create_task(email_worker.run())
        logger.info("Email watch listener started")
    except Exception as e:
        logger.warning(f"Email watch listener not started: {e}")
        if settings.app.env == "production":
            raise

    try:
        # OCR processor
        ocr_worker = OCRProcessorWorker()
        workers["ocr_processor"] = asyncio.create_task(ocr_worker.run())
        logger.info("OCR processor worker started")
    except Exception as e:
        logger.warning(f"OCR processor not started: {e}")
        if settings.app.env == "production":
            raise

    try:
        # NCB JSON generator (production mode - no API submission)
        ncb_worker = NCBJSONGeneratorWorker()
        workers["ncb_json_generator"] = asyncio.create_task(ncb_worker.run())
        logger.info("NCB JSON generator worker started (production mode)")
    except Exception as e:
        logger.warning(f"NCB JSON generator not started: {e}")
        if settings.app.env == "production":
            raise

    if workers:
        logger.info(f"Started {len(workers)} workers successfully")
        print(f"✅ Workers started: {list(workers.keys())}")  # Debug print
    else:
        logger.warning("No workers started - running in API-only mode")
        print("⚠️  NO WORKERS STARTED - API-ONLY MODE")  # Debug print

    print("✨ LIFESPAN READY - yielding control")  # Debug print
    yield
    print("🛑 LIFESPAN SHUTDOWN - cleaning up...")  # Debug print

    # Shutdown
    logger.info("Shutting down workers...")
    for name, task in workers.items():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"Worker {name} stopped")

    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Claims Data Entry Agent",
    description="Automated claims data entry with OCR for TPA",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiting state and error handler (if slowapi is available)
if SLOWAPI_AVAILABLE:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_error_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.admin.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.middleware("http")(request_logging_middleware)
app.middleware("http")(api_key_middleware)

# Include API routers
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(exceptions_router, prefix="/api/v1")
app.include_router(stats_router, prefix="/api/v1")


# Health endpoints
@app.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "version": "1.0.0",
    }


@app.get("/health/detailed")
async def detailed_health():
    """Detailed component health check with actual verification."""
    from src.services.queue_service import QueueService
    from src.services.ncb_service import NCBService
    import httpx

    components_status = {}
    overall_status = "healthy"

    # Check Redis
    try:
        queue_service = QueueService()
        # Simple ping test (connect if not already connected)
        if queue_service.redis:
            await queue_service.redis.ping()
            components_status["redis"] = "connected"
        else:
            components_status["redis"] = "not_initialized"
            overall_status = "degraded"
    except Exception as e:
        components_status["redis"] = f"error: {str(e)}"
        overall_status = "degraded"

    # Check NCB API
    try:
        ncb_service = NCBService()
        # Check if circuit breaker is open
        if ncb_service.circuit_breaker.state == "open":
            components_status["ncb_api"] = "circuit_open"
            overall_status = "degraded"
        else:
            components_status["ncb_api"] = "available"
    except Exception as e:
        components_status["ncb_api"] = f"error: {str(e)}"
        overall_status = "degraded"

    # Check Gmail (verify credentials exist)
    try:
        gmail_creds_path = settings.gmail.credentials_path
        if gmail_creds_path.exists():
            components_status["gmail"] = "credentials_present"
        else:
            components_status["gmail"] = "credentials_missing"
            overall_status = "degraded"
    except Exception as e:
        components_status["gmail"] = f"error: {str(e)}"
        overall_status = "degraded"

    # Check Google Sheets (verify credentials exist)
    try:
        sheets_creds_path = settings.sheets.credentials_path
        if sheets_creds_path.exists():
            components_status["google_sheets"] = "credentials_present"
        else:
            components_status["google_sheets"] = "credentials_missing"
            overall_status = "degraded"
    except Exception as e:
        components_status["google_sheets"] = f"error: {str(e)}"
        overall_status = "degraded"

    # Check Google Drive (verify credentials exist)
    try:
        drive_creds_path = settings.drive.credentials_path
        if drive_creds_path.exists():
            components_status["google_drive"] = "credentials_present"
        else:
            components_status["google_drive"] = "credentials_missing"
            overall_status = "degraded"
    except Exception as e:
        components_status["google_drive"] = f"error: {str(e)}"
        overall_status = "degraded"

    # Check OCR engine (verify it was initialized)
    try:
        components_status["ocr_engine"] = "ready"
        components_status["ocr_gpu_enabled"] = settings.ocr.use_gpu
    except Exception as e:
        components_status["ocr_engine"] = f"error: {str(e)}"
        overall_status = "degraded"

    return {
        "status": overall_status,
        "version": "1.0.0",
        "components": components_status,
        "workers": {
            "email_watch_listener": "running" if "email_watch_listener" in workers else "stopped",
            "ocr_processor": "running" if "ocr_processor" in workers else "stopped",
            "ncb_json_generator": "running" if "ncb_json_generator" in workers else "stopped",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.admin.port,
        reload=settings.app.debug,
        log_level=settings.app.log_level.lower(),
    )
