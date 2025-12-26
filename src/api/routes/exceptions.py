"""Exception queue management API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from src.api.models import (
    ExceptionApprovalRequest,
    ExceptionApprovalResponse,
    ExceptionDetailResponse,
    ExceptionListResponse,
    ExceptionRejectionRequest,
    ExceptionRejectionResponse,
)
from src.models.claim import ExtractedClaim, NCBSubmissionRequest
from src.models.job import JobStatus
from src.services.ncb_service import NCBService
from src.services.queue_service import QueueService
from src.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/exceptions", tags=["Exceptions"])

# Service instances
queue_service = QueueService()
ncb_service = NCBService()


@router.get("", response_model=ExceptionListResponse)
async def list_exceptions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> ExceptionListResponse:
    """
    List jobs in exception queue requiring manual review.

    **Returns:**
    - Jobs with confidence < 75% or extraction errors
    - Extracted data with field-level confidence scores
    - Warnings and error messages

    **Pagination:**
    - `page`: Page number (1-indexed)
    - `page_size`: Number of items per page (max 100)
    """
    try:
        # Get exception queue
        exception_jobs = await queue_service.get_exception_queue()

        # Sort by created_at descending (newest first)
        exception_jobs.sort(key=lambda j: j.created_at, reverse=True)

        # Calculate pagination
        total = len(exception_jobs)
        total_pages = (total + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # Get page items
        page_jobs = exception_jobs[start_idx:end_idx]

        # Convert to response models
        items = []
        for job in page_jobs:
            item_data = {
                "id": job.id,
                "email_id": job.email_id,
                "attachment_filename": job.attachment_filename,
                "error_message": job.error_message,
                "retry_count": job.retry_count,
                "created_at": job.created_at,
            }

            # Add extraction data if available
            if job.extraction_result:
                item_data["confidence_score"] = job.extraction_result.confidence_score
                item_data["confidence_level"] = job.extraction_result.confidence_level
                item_data["field_confidences"] = job.extraction_result.field_confidences
                item_data["warnings"] = job.extraction_result.warnings

                claim = job.extraction_result.claim
                item_data["member_id"] = claim.member_id
                item_data["member_name"] = claim.member_name
                item_data["provider_name"] = claim.provider_name
                item_data["service_date"] = claim.service_date
                item_data["receipt_number"] = claim.receipt_number
                item_data["total_amount"] = claim.total_amount
            else:
                # Default confidence if no extraction
                item_data["confidence_score"] = 0.0
                item_data["confidence_level"] = "low"

            items.append(ExceptionDetailResponse(**item_data))

        logger.info(
            "Exception queue listed",
            total=total,
            page=page,
            page_size=page_size
        )

        return ExceptionListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        )

    except Exception as e:
        logger.error("Failed to list exceptions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list exceptions: {str(e)}"
        )


@router.post("/{job_id}/approve", response_model=ExceptionApprovalResponse)
async def approve_exception(
    job_id: str,
    request: Optional[ExceptionApprovalRequest] = None,
) -> ExceptionApprovalResponse:
    """
    Approve exception and submit to NCB.

    **Actions:**
    1. Optionally override extracted data with corrections
    2. Submit to NCB API
    3. Update job status to SUBMITTED
    4. Remove from exception queue

    **Request Body (optional):**
    - `override_data`: Corrected claim data to override extraction

    **Returns:**
    - NCB claim reference number
    - Success/failure status
    """
    try:
        job = await queue_service.get_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        if job.status != JobStatus.EXCEPTION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job is not in exception status. Current status: {job.status}"
            )

        # Get claim data
        if not job.extraction_result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job has no extraction result to submit"
            )

        claim = job.extraction_result.claim

        # Apply overrides if provided
        if request and request.override_data:
            for key, value in request.override_data.items():
                if hasattr(claim, key):
                    setattr(claim, key, value)
            logger.info(
                "Applied data overrides",
                job_id=job_id,
                overrides=request.override_data
            )

        # Validate required fields
        if not all([
            claim.service_date,
            claim.total_amount,
            claim.receipt_number,
            claim.policy_number,
        ]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields for NCB submission"
            )

        # Create NCB submission request
        submission = NCBSubmissionRequest(
            **{
                "Event date": claim.service_date.strftime("%Y-%m-%d"),
                "Submission Date": datetime.now().strftime("%Y-%m-%d"),
                "Claim Amount": claim.total_amount,
                "Invoice Number": claim.receipt_number,
                "Policy Number": claim.policy_number,
            },
            source_email_id=job.email_id,
            source_filename=job.attachment_filename,
            extraction_confidence=job.extraction_result.confidence_score,
        )

        # Submit to NCB
        ncb_response = await ncb_service.submit_claim(submission)

        if not ncb_response.success:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"NCB submission failed: {ncb_response.error_message}"
            )

        # Update job status
        await queue_service.update_job_status(
            job_id,
            JobStatus.SUBMITTED,
            ncb_reference=ncb_response.claim_reference,
            ncb_submitted_at=datetime.now(),
        )

        # Remove from exception queue
        await queue_service.remove_from_exception_queue(job_id)

        logger.info(
            "Exception approved and submitted",
            job_id=job_id,
            ncb_reference=ncb_response.claim_reference
        )

        return ExceptionApprovalResponse(
            success=True,
            job_id=job_id,
            ncb_reference=ncb_response.claim_reference,
            message="Exception approved and submitted to NCB successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to approve exception", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve exception: {str(e)}"
        )


@router.post("/{job_id}/reject", response_model=ExceptionRejectionResponse)
async def reject_exception(
    job_id: str,
    request: ExceptionRejectionRequest,
) -> ExceptionRejectionResponse:
    """
    Reject exception and mark job as rejected.

    **Actions:**
    1. Update job status to REJECTED
    2. Record rejection reason
    3. Remove from exception queue

    **Request Body:**
    - `reason`: Reason for rejection (required)

    **Returns:**
    - Success/failure status
    """
    try:
        job = await queue_service.get_job(job_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        if job.status != JobStatus.EXCEPTION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job is not in exception status. Current status: {job.status}"
            )

        # Update job status
        await queue_service.update_job_status(
            job_id,
            JobStatus.REJECTED,
            error_message=f"Rejected: {request.reason}",
        )

        # Remove from exception queue
        await queue_service.remove_from_exception_queue(job_id)

        logger.info(
            "Exception rejected",
            job_id=job_id,
            reason=request.reason
        )

        return ExceptionRejectionResponse(
            success=True,
            job_id=job_id,
            message=f"Exception rejected: {request.reason}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reject exception", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject exception: {str(e)}"
        )
