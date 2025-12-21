"""Main FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings
from src.utils.logging import configure_logging, get_logger
from src.workers.email_poller import EmailPollerWorker
from src.workers.ncb_submitter import NCBSubmitterWorker
from src.workers.ocr_processor import OCRProcessorWorker

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Worker instances
workers = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    logger.info("Starting Claims Data Entry Agent", env=settings.app.env)

    # Start background workers
    logger.info("Starting background workers...")

    # Email poller
    email_worker = EmailPollerWorker()
    workers["email_poller"] = asyncio.create_task(email_worker.run())

    # OCR processor
    ocr_worker = OCRProcessorWorker()
    workers["ocr_processor"] = asyncio.create_task(ocr_worker.run())

    # NCB submitter
    ncb_worker = NCBSubmitterWorker()
    workers["ncb_submitter"] = asyncio.create_task(ncb_worker.run())

    logger.info("All workers started")

    yield

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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.admin.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    """Detailed component health check."""
    # TODO: Implement component health checks
    return {
        "status": "healthy",
        "version": "1.0.0",
        "components": {
            "redis": "connected",
            "gmail": "connected",
            "ncb_api": "connected",
            "google_sheets": "connected",
            "google_drive": "connected",
            "ocr_engine": "ready",
        },
        "workers": {
            "email_poller": "running" if "email_poller" in workers else "stopped",
            "ocr_processor": "running" if "ocr_processor" in workers else "stopped",
            "ncb_submitter": "running" if "ncb_submitter" in workers else "stopped",
        },
    }


# API endpoints will be added in Phase 2
# from src.api.routes import health, jobs, exceptions, stats
# app.include_router(health.router)
# app.include_router(jobs.router, prefix="/api/v1")
# app.include_router(exceptions.router, prefix="/api/v1")
# app.include_router(stats.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.admin.port,
        reload=settings.app.debug,
        log_level=settings.app.log_level.lower(),
    )
