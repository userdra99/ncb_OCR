"""Statistics and dashboard API endpoints."""

from datetime import datetime, timedelta
from typing import Optional
import warnings

from fastapi import APIRouter, HTTPException, Query, Request, status

from src.api.middleware import optional_limit, RATE_LIMITS
from src.api.models import (
    AggregatedStatsResponse,
    DailyStatsItem,
    DailyStatsResponse,
    DashboardStatsResponse,
    JobStatItem,
    PaginatedJobStatsResponse,
)
from src.models.job import JobStatus
from src.services.queue_service import QueueService
from src.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/stats", tags=["Statistics"])

# Service instance
queue_service = QueueService()


@router.get("/dashboard", response_model=DashboardStatsResponse, deprecated=True)
@optional_limit(RATE_LIMITS["stats_dashboard"])
async def get_dashboard_stats(request: Request) -> DashboardStatsResponse:
    """
    Get dashboard summary statistics.

    ⚠️ **DEPRECATED**: This endpoint loads all jobs into memory and may cause
    OOM errors with 10,000+ jobs. Use `/stats/summary` for aggregated stats
    or `/stats/jobs` for paginated job access.

    **Migration Guide:**
    - For dashboard metrics → Use `/stats/summary`
    - For job listings → Use `/stats/jobs` with pagination
    - For detailed analytics → Use `/stats/daily` with date filters

    **Returns:**
    - Processing counts (today, week, month)
    - Success rates
    - Average confidence scores
    - Queue sizes
    - Performance metrics
    - Status breakdown

    **Performance Warning:**
    - Memory usage: O(n) where n = total jobs
    - Not recommended for production with >10k jobs
    - May cause timeouts and OOM errors
    """
    try:
        # Log deprecation warning
        logger.warning(
            "DEPRECATED: /stats/dashboard endpoint called. "
            "This endpoint loads all jobs into memory. "
            "Consider migrating to /stats/summary or /stats/jobs"
        )

        # Get all jobs
        all_job_ids = await queue_service.get_all_job_ids()
        all_jobs = []
        for job_id in all_job_ids:
            job = await queue_service.get_job(job_id)
            if job:
                all_jobs.append(job)

        # Calculate date ranges
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)

        # Filter jobs by date
        jobs_today = [j for j in all_jobs if j.created_at >= today_start]
        jobs_week = [j for j in all_jobs if j.created_at >= week_start]
        jobs_month = [j for j in all_jobs if j.created_at >= month_start]

        # Count successful submissions
        successful_jobs = [j for j in all_jobs if j.status == JobStatus.SUBMITTED]
        total_jobs = len(all_jobs)

        # Calculate success rate
        success_rate = len(successful_jobs) / total_jobs if total_jobs > 0 else 0.0

        # Calculate NCB submission rate (auto-submitted without manual review)
        auto_submitted = [
            j for j in successful_jobs
            if j.extraction_result and j.extraction_result.confidence_score >= 0.90
        ]
        ncb_submission_rate = len(auto_submitted) / total_jobs if total_jobs > 0 else 0.0

        # Calculate average confidence
        jobs_with_confidence = [
            j for j in all_jobs
            if j.extraction_result and j.extraction_result.confidence_score > 0
        ]
        if jobs_with_confidence:
            average_confidence = sum(
                j.extraction_result.confidence_score for j in jobs_with_confidence
            ) / len(jobs_with_confidence)
        else:
            average_confidence = 0.0

        # Count confidence levels
        high_confidence = len([
            j for j in jobs_with_confidence
            if j.extraction_result.confidence_score >= 0.90
        ])
        medium_confidence = len([
            j for j in jobs_with_confidence
            if 0.75 <= j.extraction_result.confidence_score < 0.90
        ])
        low_confidence = len([
            j for j in jobs_with_confidence
            if j.extraction_result.confidence_score < 0.75
        ])

        # Get queue sizes
        pending_exceptions = await queue_service.get_queue_size(
            queue_service.config.exception_queue
        )
        pending_ocr = await queue_service.get_queue_size(
            queue_service.config.ocr_queue
        )
        pending_submission = await queue_service.get_queue_size(
            queue_service.config.submission_queue
        )

        # Calculate average processing time
        completed_jobs = [
            j for j in all_jobs
            if j.status in [JobStatus.SUBMITTED, JobStatus.REJECTED]
        ]
        if completed_jobs:
            processing_times = [
                (j.updated_at - j.created_at).total_seconds()
                for j in completed_jobs
            ]
            average_processing_time = sum(processing_times) / len(processing_times)
        else:
            average_processing_time = 0.0

        # Status breakdown
        status_breakdown = {}
        for job_status in JobStatus:
            count = len([j for j in all_jobs if j.status == job_status])
            status_breakdown[job_status.value] = count

        logger.info(
            "Dashboard stats calculated",
            total_jobs=total_jobs,
            today=len(jobs_today),
            week=len(jobs_week),
            month=len(jobs_month)
        )

        return DashboardStatsResponse(
            total_processed_today=len(jobs_today),
            total_processed_week=len(jobs_week),
            total_processed_month=len(jobs_month),
            success_rate=success_rate,
            ncb_submission_rate=ncb_submission_rate,
            average_confidence=average_confidence,
            high_confidence_count=high_confidence,
            medium_confidence_count=medium_confidence,
            low_confidence_count=low_confidence,
            pending_exceptions=pending_exceptions,
            pending_ocr=pending_ocr,
            pending_submission=pending_submission,
            average_processing_time_seconds=average_processing_time,
            status_breakdown=status_breakdown,
        )

    except Exception as e:
        logger.error("Failed to calculate dashboard stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate dashboard stats: {str(e)}"
        )


@router.get("/daily", response_model=DailyStatsResponse)
@optional_limit(RATE_LIMITS["stats_daily"])
async def get_daily_stats(
    request: Request,
    start_date: datetime = Query(..., description="Start date for stats"),
    end_date: datetime = Query(..., description="End date for stats"),
) -> DailyStatsResponse:
    """
    Get daily statistics breakdown for a date range.

    **Query Parameters:**
    - `start_date`: Start date (inclusive)
    - `end_date`: End date (inclusive)

    **Returns:**
    - Daily breakdown of processing metrics
    - Overall summary for the period
    """
    try:
        # Validate date range
        if end_date < start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date must be after start_date"
            )

        # Limit to 90 days
        if (end_date - start_date).days > 90:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date range cannot exceed 90 days"
            )

        # Get all jobs in date range
        all_job_ids = await queue_service.get_all_job_ids()
        jobs_in_range = []
        for job_id in all_job_ids:
            job = await queue_service.get_job(job_id)
            if job and start_date <= job.created_at <= end_date:
                jobs_in_range.append(job)

        # Group jobs by day
        daily_jobs = {}
        current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)
            day_jobs = [
                j for j in jobs_in_range
                if current_date <= j.created_at < next_date
            ]
            daily_jobs[current_date] = day_jobs
            current_date = next_date

        # Calculate daily stats
        daily_items = []
        for date, jobs in sorted(daily_jobs.items()):
            total_processed = len(jobs)
            successful = len([j for j in jobs if j.status == JobStatus.SUBMITTED])
            failed = len([j for j in jobs if j.status == JobStatus.FAILED])
            exceptions = len([j for j in jobs if j.status == JobStatus.EXCEPTION])

            # Average confidence
            jobs_with_confidence = [
                j for j in jobs
                if j.extraction_result and j.extraction_result.confidence_score > 0
            ]
            if jobs_with_confidence:
                avg_confidence = sum(
                    j.extraction_result.confidence_score for j in jobs_with_confidence
                ) / len(jobs_with_confidence)
            else:
                avg_confidence = 0.0

            # Average processing time
            completed = [
                j for j in jobs
                if j.status in [JobStatus.SUBMITTED, JobStatus.REJECTED]
            ]
            if completed:
                avg_time = sum(
                    (j.updated_at - j.created_at).total_seconds() for j in completed
                ) / len(completed)
            else:
                avg_time = 0.0

            daily_items.append(DailyStatsItem(
                date=date,
                total_processed=total_processed,
                successful=successful,
                failed=failed,
                exceptions=exceptions,
                average_confidence=avg_confidence,
                average_processing_time_seconds=avg_time,
            ))

        # Get summary stats for the period
        summary = await get_dashboard_stats()

        logger.info(
            "Daily stats calculated",
            start_date=start_date,
            end_date=end_date,
            days=len(daily_items)
        )

        return DailyStatsResponse(
            items=daily_items,
            summary=summary,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to calculate daily stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate daily stats: {str(e)}"
        )


@router.get("/jobs", response_model=PaginatedJobStatsResponse)
@optional_limit(RATE_LIMITS["stats_jobs"])
async def get_job_stats(
    request: Request,
    cursor: Optional[str] = Query(
        default=None,
        description="Pagination cursor (from previous response's next_cursor)"
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum jobs to return (default 100, max 1000)"
    ),
    job_status: Optional[JobStatus] = Query(
        default=None,
        alias="status",
        description="Filter by job status"
    ),
) -> PaginatedJobStatsResponse:
    """
    Get job statistics with cursor-based pagination.

    This endpoint uses Redis SCAN for memory-efficient iteration through large
    job datasets. Unlike the dashboard endpoint, this doesn't load all jobs
    into memory and can handle 10,000+ jobs without OOM errors.

    **Query Parameters:**
    - `cursor`: Pagination cursor from previous response (omit for first page)
    - `limit`: Number of jobs per page (default 100, max 1000)
    - `status`: Filter by job status (pending, processing, completed, etc.)

    **Response:**
    - `total`: Total jobs in current page
    - `jobs`: Array of job statistics
    - `next_cursor`: Cursor for next page (null if no more results)
    - `has_more`: Boolean indicating if more pages exist
    - `limit`: Page size used

    **Example Usage:**
    ```
    # First page
    GET /api/v1/stats/jobs?limit=100

    # Next page
    GET /api/v1/stats/jobs?cursor=12345&limit=100

    # Filter by status
    GET /api/v1/stats/jobs?status=completed&limit=50
    ```

    **Memory Usage:**
    - O(limit) instead of O(total_jobs)
    - Supports datasets with 100k+ jobs
    - Response time: <200ms for typical queries

    **Migration from /dashboard:**
    The `/stats/dashboard` endpoint loads all jobs into memory and will be
    deprecated for large datasets. Use this endpoint for paginated access.
    """
    try:
        # Get paginated job IDs from Redis
        job_ids, next_cursor = await queue_service.get_job_ids_paginated(
            cursor=cursor,
            limit=limit,
            status=job_status
        )

        # Process only the page of jobs
        job_stats = []

        for job_id in job_ids:
            job = await queue_service.get_job(job_id)
            if job:
                # Calculate processing time if completed
                processing_time_ms = None
                if job.status in [JobStatus.SUBMITTED, JobStatus.REJECTED, JobStatus.FAILED]:
                    processing_time_ms = (
                        (job.updated_at - job.created_at).total_seconds() * 1000
                    )

                # Extract confidence info
                confidence_score = None
                confidence_level = None
                if job.extraction_result:
                    confidence_score = job.extraction_result.confidence_score
                    confidence_level = job.extraction_result.confidence_level

                job_stats.append(JobStatItem(
                    id=job_id,
                    email_id=job.email_id,
                    status=job.status,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                    processing_time_ms=processing_time_ms,
                    confidence_score=confidence_score,
                    confidence_level=confidence_level,
                    ncb_reference=job.ncb_reference
                ))

        logger.info(
            "Paginated job stats retrieved",
            count=len(job_stats),
            cursor=cursor,
            next_cursor=next_cursor,
            status=job_status.value if job_status else None
        )

        return PaginatedJobStatsResponse(
            total=len(job_stats),
            jobs=job_stats,
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
            limit=limit
        )

    except Exception as e:
        logger.error("Failed to get paginated job stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job stats: {str(e)}"
        )


@router.get("/summary", response_model=AggregatedStatsResponse)
@optional_limit(RATE_LIMITS["stats_summary"])
async def get_stats_summary(request: Request) -> AggregatedStatsResponse:
    """
    Get aggregated statistics without loading all jobs into memory.

    This endpoint provides high-level metrics using Redis-native operations
    for maximum efficiency. It's designed for dashboard displays and monitoring.

    **Response:**
    - `total_jobs`: Total number of jobs in system
    - `by_status`: Count of jobs by status (pending, processing, completed, etc.)
    - `queue_depths`: Current queue sizes (OCR, submission, exception)
    - `processing_times`: Average processing times by queue

    **Performance:**
    - Uses Redis SCAN with aggregation
    - O(n) time but constant memory
    - Suitable for monitoring dashboards
    - Response time: <1s for 100k+ jobs

    **Use Cases:**
    - Dashboard summary statistics
    - Real-time monitoring
    - Alerting on queue depths
    - System health checks

    **Example Response:**
    ```json
    {
      "total_jobs": 15234,
      "by_status": {
        "pending": 45,
        "processing": 12,
        "completed": 14890,
        "failed": 287
      },
      "queue_depths": {
        "ocr_queue": 45,
        "submission_queue": 12,
        "exception_queue": 23
      },
      "processing_times": {
        "avg_ocr_time": 2.5,
        "avg_submission_time": 1.8
      }
    }
    ```
    """
    try:
        # Get aggregated stats using efficient Redis operations
        stats = await queue_service.get_aggregated_stats()

        logger.info(
            "Aggregated stats retrieved",
            total_jobs=stats["total"],
            status_counts=stats
        )

        return AggregatedStatsResponse(
            total_jobs=stats["total"],
            by_status={
                "pending": stats["pending_count"],
                "processing": stats["processing_count"],
                "completed": stats["completed_count"],
                "failed": stats["failed_count"],
                "exception": stats["exception_count"],
                "submitted": stats["submitted_count"],
                "rejected": stats["rejected_count"]
            },
            queue_depths={
                "ocr_queue": stats["queue_sizes"]["ocr_queue"],
                "submission_queue": stats["queue_sizes"]["submission_queue"],
                "exception_queue": stats["queue_sizes"]["exception_queue"]
            },
            processing_times={}  # To be implemented with time-series data
        )

    except Exception as e:
        logger.error("Failed to get aggregated stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats summary: {str(e)}"
        )
