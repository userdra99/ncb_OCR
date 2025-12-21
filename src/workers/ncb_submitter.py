"""NCB submitter worker for claim submission."""

import asyncio
from datetime import datetime

from src.config.settings import settings
from src.models.claim import NCBSubmissionRequest
from src.models.job import JobStatus
from src.services.ncb_service import (
    NCBConnectionError,
    NCBRateLimitError,
    NCBService,
    NCBValidationError,
)
from src.services.queue_service import QueueService
from src.services.sheets_service import SheetsService
from src.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


class NCBSubmitterWorker:
    """
    NCB submitter worker.

    Submits extracted claims to NCB API:
    - Pulls jobs from submission queue
    - Builds NCB request payload
    - Submits with retry logic
    - Updates job status
    - Updates Sheets with NCB reference
    """

    def __init__(self) -> None:
        """Initialize worker."""
        self.ncb_service = NCBService()
        self.queue_service = QueueService()
        self.sheets_service = SheetsService()
        self.running = False
        logger.info("NCB submitter worker initialized")

    async def run(self) -> None:
        """Main worker loop."""
        self.running = True
        await self.queue_service.connect()

        logger.info("NCB submitter worker started")

        while self.running:
            try:
                # Dequeue job from submission queue
                job = await self.queue_service.dequeue_job(
                    settings.redis.submission_queue, timeout=1
                )

                if job:
                    await self._submit_job(job)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
                break
            except Exception as e:
                logger.error("Submission error", error=str(e))
                await asyncio.sleep(1)

        await self.queue_service.disconnect()
        logger.info("NCB submitter worker stopped")

    async def stop(self) -> None:
        """Stop worker gracefully."""
        logger.info("Stopping NCB submitter worker...")
        self.running = False

    async def _submit_job(self, job) -> None:
        """
        Submit single job to NCB API.

        Steps:
        1. Build NCB request
        2. Attempt submission
        3. Handle response
        4. Update job status
        5. Update Sheets
        """
        logger.info(
            "Submitting job to NCB",
            job_id=job.id,
            member_id=job.extraction_result.claim.member_id,
        )

        try:
            # Validate required fields
            claim = job.extraction_result.claim
            if not claim.member_id or not claim.total_amount:
                logger.error(
                    "Missing required fields for NCB submission",
                    job_id=job.id,
                )
                await self.queue_service.update_job_status(
                    job.id,
                    JobStatus.EXCEPTION,
                    error_message="Missing required fields (member_id or total_amount)",
                )
                return

            # Build NCB request
            ncb_request = NCBSubmissionRequest(
                member_id=claim.member_id,
                member_name=claim.member_name or "Unknown",
                provider_name=claim.provider_name or "Unknown Provider",
                provider_address=claim.provider_address,
                service_date=claim.service_date.isoformat() if claim.service_date else "",
                receipt_number=claim.receipt_number or "",
                total_amount=claim.total_amount,
                currency=claim.currency,
                itemized_charges=(
                    [charge.model_dump() for charge in claim.itemized_charges]
                    if claim.itemized_charges
                    else None
                ),
                gst_amount=claim.gst_amount,
                sst_amount=claim.sst_amount,
                source_email_id=job.email_id,
                source_filename=job.attachment_filename,
                extraction_confidence=job.extraction_result.confidence_score,
            )

            # Submit to NCB (with automatic retry via tenacity decorator)
            response = await self.ncb_service.submit_claim(ncb_request)

            if response.success:
                # Update job status
                await self.queue_service.update_job_status(
                    job.id,
                    JobStatus.SUBMITTED,
                    ncb_reference=response.claim_reference,
                    ncb_submitted_at=datetime.now(),
                )

                # Update Sheets
                if job.sheets_row_ref:
                    try:
                        await self.sheets_service.update_ncb_status(
                            job.sheets_row_ref,
                            response.claim_reference or "",
                            "submitted",
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to update Sheets",
                            job_id=job.id,
                            error=str(e),
                        )

                logger.info(
                    "Job submitted successfully",
                    job_id=job.id,
                    ncb_reference=response.claim_reference,
                )

            else:
                # Submission failed
                logger.error(
                    "NCB submission failed",
                    job_id=job.id,
                    error_code=response.error_code,
                    error_message=response.error_message,
                )
                await self.queue_service.update_job_status(
                    job.id,
                    JobStatus.FAILED,
                    error_message=response.error_message,
                )

        except NCBValidationError as e:
            # Validation error - route to exception queue
            logger.warning(
                "NCB validation error, routing to exception queue",
                job_id=job.id,
                error=str(e),
            )
            await self.queue_service.update_job_status(
                job.id, JobStatus.EXCEPTION, error_message=f"Validation error: {e}"
            )

        except NCBRateLimitError as e:
            # Rate limited - requeue with delay
            logger.warning("NCB rate limit hit, requeuing job", job_id=job.id, error=str(e))
            await asyncio.sleep(60)  # Wait 1 minute
            await self.queue_service.enqueue_job(
                job, queue_name=settings.redis.submission_queue
            )

        except NCBConnectionError as e:
            # Connection error - retry logic handled by tenacity
            logger.error("NCB connection error after retries", job_id=job.id, error=str(e))
            await self.queue_service.update_job_status(
                job.id,
                JobStatus.FAILED,
                error_message=f"NCB connection error: {e}",
                retry_count=job.retry_count + 1,
            )

        except Exception as e:
            logger.error("Unexpected submission error", job_id=job.id, error=str(e))
            await self.queue_service.update_job_status(
                job.id, JobStatus.FAILED, error_message=str(e)
            )


async def main():
    """Entry point for NCB submitter worker."""
    worker = NCBSubmitterWorker()
    try:
        await worker.run()
    except KeyboardInterrupt:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
