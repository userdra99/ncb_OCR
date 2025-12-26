"""Job management API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from src.api.models import (
    JobDetailResponse,
    JobListParams,
    JobListResponse,
    JobRetryResponse,
)
from src.models.job import Job, JobStatus
from src.services.queue_service import QueueService
from src.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["Jobs"])

# Service instance
queue_service = QueueService()


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status_filter: Optional[JobStatus] = Query(None, alias="status", description="Filter by job status"),
    start_date: Optional[datetime] = Query(None, description="Filter jobs created after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter jobs created before this date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> JobListResponse:
    """
    List jobs with optional filtering and pagination.

    **Filters:**
    - `status`: Filter by job status (pending, processing, extracted, submitted, exception, rejected, failed)
    - `start_date`: Only show jobs created after this date
    - `end_date`: Only show jobs created before this date

    **Pagination:**
    - `page`: Page number (1-indexed)
    - `page_size`: Number of items per page (max 100)
    """
    try:
        # Get all job IDs from Redis
        all_job_ids = await queue_service.get_all_job_ids()

        # Fetch and filter jobs
        filtered_jobs = []
        for job_id in all_job_ids:
            job = await queue_service.get_job(job_id)
            if not job:
                continue

            # Apply filters
            if status_filter and job.status != status_filter:
                continue

            if start_date and job.created_at < start_date:
                continue

            if end_date and job.created_at > end_date:
                continue

            filtered_jobs.append(job)

        # Sort by created_at descending (newest first)
        filtered_jobs.sort(key=lambda j: j.created_at, reverse=True)

        # Calculate pagination
        total = len(filtered_jobs)
        total_pages = (total + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # Get page items
        page_jobs = filtered_jobs[start_idx:end_idx]

        # Convert to response models
        items = [_job_to_detail_response(job) for job in page_jobs]

        logger.info(
            "Jobs listed",
            total=total,
            page=page,
            page_size=page_size,
            filters={"status": status_filter, "start_date": start_date, "end_date": end_date}
        )

        return JobListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        )

    except Exception as e:
        logger.error("Failed to list jobs", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list jobs: {str(e)}"
        )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job_details(job_id: str) -> JobDetailResponse:
    """
    Get detailed information about a specific job.

    **Returns:**
    - Full job details including extraction results
    - NCB submission status
    - Google Sheets and Drive references
    - Error messages if any
    """
    try:
        job = await queue_service.get_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        logger.info("Job details retrieved", job_id=job_id, status=job.status)

        return _job_to_detail_response(job)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job details", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job details: {str(e)}"
        )


@router.post("/{job_id}/retry", response_model=JobRetryResponse)
async def retry_failed_job(job_id: str) -> JobRetryResponse:
    """
    Retry a failed job by re-queuing it for OCR processing.

    **Conditions:**
    - Job must exist
    - Job status must be FAILED or EXCEPTION
    - Retry count must be less than max retries (3)

    **Actions:**
    - Resets job status to PENDING
    - Increments retry count
    - Re-queues job for OCR processing
    """
    try:
        job = await queue_service.get_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        # Check if job can be retried
        if job.status not in [JobStatus.FAILED, JobStatus.EXCEPTION]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job cannot be retried. Current status: {job.status}"
            )

        # Check retry limit
        max_retries = 3
        if job.retry_count >= max_retries:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job has reached maximum retry limit ({max_retries})"
            )

        # Update job and re-queue
        job.status = JobStatus.PENDING
        job.retry_count += 1
        job.updated_at = datetime.now()
        job.error_message = None  # Clear previous error

        # Save updated job
        await queue_service.enqueue_job(job, queue_name=queue_service.config.ocr_queue)

        logger.info(
            "Job retried",
            job_id=job_id,
            retry_count=job.retry_count,
            new_status=job.status
        )

        return JobRetryResponse(
            success=True,
            job_id=job_id,
            message=f"Job re-queued for processing (retry {job.retry_count}/{max_retries})",
            new_status=job.status,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retry job", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry job: {str(e)}"
        )


def _job_to_detail_response(job: Job) -> JobDetailResponse:
    """Convert Job model to JobDetailResponse."""
    response_data = {
        "id": job.id,
        "email_id": job.email_id,
        "attachment_filename": job.attachment_filename,
        "status": job.status,
        "ncb_reference": job.ncb_reference,
        "ncb_submitted_at": job.ncb_submitted_at,
        "sheets_row_ref": job.sheets_row_ref,
        "drive_file_id": job.drive_file_id,
        "error_message": job.error_message,
        "retry_count": job.retry_count,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }

    # Add extraction data if available
    if job.extraction_result:
        response_data["confidence_score"] = job.extraction_result.confidence_score
        response_data["confidence_level"] = job.extraction_result.confidence_level

        claim = job.extraction_result.claim
        response_data["member_id"] = claim.member_id
        response_data["member_name"] = claim.member_name
        response_data["provider_name"] = claim.provider_name
        response_data["service_date"] = claim.service_date
        response_data["total_amount"] = claim.total_amount

    return JobDetailResponse(**response_data)
