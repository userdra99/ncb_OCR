"""OCR processor worker for text extraction."""

import asyncio
import random
from pathlib import Path

from src.config.settings import settings
from src.models.job import JobStatus
from src.services.drive_service import DriveService
from src.services.ocr_service import OCRService
from src.services.queue_service import QueueService
from src.services.sheets_service import SheetsService
from src.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


class OCRProcessorWorker:
    """
    OCR processor worker.

    Processes images through OCR pipeline:
    - Extracts text and structured data
    - Calculates confidence scores
    - Routes based on confidence threshold
    - Logs to Sheets
    - Archives to Drive
    """

    def __init__(self) -> None:
        """Initialize worker."""
        self.ocr_service = OCRService()
        self.queue_service = QueueService()
        self.sheets_service = SheetsService()
        self.drive_service = DriveService()
        self.running = False
        logger.info("OCR processor worker initialized")

    async def run(self) -> None:
        """Main worker loop."""
        self.running = True
        await self.queue_service.connect()

        logger.info("OCR processor worker started")

        while self.running:
            try:
                # Dequeue job from OCR queue
                job = await self.queue_service.dequeue_job(
                    settings.redis.ocr_queue, timeout=1
                )

                if job:
                    await self._process_job(job)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
                break
            except Exception as e:
                logger.error("Processing error", error=str(e))
                await asyncio.sleep(1)

        await self.queue_service.disconnect()
        logger.info("OCR processor worker stopped")

    async def stop(self) -> None:
        """Stop worker gracefully."""
        logger.info("Stopping OCR processor worker...")
        self.running = False

    async def _process_job(self, job) -> None:
        """
        Process single job through OCR pipeline.

        Steps:
        1. Load image
        2. Run OCR extraction
        3. Structure data
        4. Calculate confidence
        5. Route based on confidence
        6. Log to Sheets
        7. Archive to Drive
        """
        logger.info(
            "Processing job",
            job_id=job.id,
            email_id=job.email_id,
            filename=job.attachment_filename,
        )

        try:
            # Update status to processing
            await self.queue_service.update_job_status(job.id, JobStatus.PROCESSING)

            # Run OCR extraction
            image_path = Path(job.attachment_path)
            extraction_result = await self.ocr_service.extract_structured_data(image_path)

            # Update job with extraction result
            await self.queue_service.update_job_status(
                job.id,
                JobStatus.EXTRACTED,
                extraction_result=extraction_result,
            )

            # Get updated job
            job = await self.queue_service.get_job(job.id)

            # Log to Sheets
            try:
                row_ref = await self.sheets_service.log_extraction(job, extraction_result)
                await self.queue_service.update_job_status(
                    job.id, JobStatus.EXTRACTED, sheets_row_ref=row_ref
                )
            except Exception as e:
                logger.error("Failed to log to Sheets", job_id=job.id, error=str(e))

            # Archive to Drive
            try:
                drive_file_id = await self.drive_service.archive_attachment(
                    image_path, job.email_id, job.attachment_filename
                )
                await self.queue_service.update_job_status(
                    job.id, JobStatus.EXTRACTED, drive_file_id=drive_file_id
                )
            except Exception as e:
                logger.error("Failed to archive to Drive", job_id=job.id, error=str(e))

            # Route based on confidence and QA sampling
            confidence = extraction_result.confidence_score

            # Check if job should be routed to exception queue
            should_route_to_exception = False
            exception_reason = None
            needs_review = False

            # Check confidence thresholds
            if confidence < settings.ocr.medium_confidence_threshold:
                # Low confidence - route to exception queue
                should_route_to_exception = True
                exception_reason = f"Low confidence: {confidence:.2%}"
                logger.warning(
                    "Low confidence extraction, routing to exception queue",
                    job_id=job.id,
                    confidence=confidence,
                    threshold=settings.ocr.medium_confidence_threshold,
                )

            elif confidence < settings.ocr.high_confidence_threshold:
                # Medium confidence - mark for review but proceed
                needs_review = True
                logger.info(
                    "Medium confidence extraction, marking for review",
                    job_id=job.id,
                    confidence=confidence,
                    medium_threshold=settings.ocr.medium_confidence_threshold,
                    high_threshold=settings.ocr.high_confidence_threshold,
                )

            else:
                # High confidence - check for QA random sampling
                qa_sample_rate = settings.ocr.qa_sampling_percentage
                if random.random() < qa_sample_rate:
                    needs_review = True
                    exception_reason = f"QA random sampling ({qa_sample_rate:.1%} rate)"
                    logger.info(
                        "High confidence extraction selected for QA sampling",
                        job_id=job.id,
                        confidence=confidence,
                        qa_sample_rate=qa_sample_rate,
                    )

            # Get fresh job data
            job = await self.queue_service.get_job(job.id)

            if should_route_to_exception:
                # Route to exception queue
                await self.queue_service.update_job_status(
                    job.id,
                    JobStatus.EXCEPTION,
                    exception_reason=exception_reason,
                    needs_review=True,
                )
                logger.info(
                    "Job routed to exception queue",
                    job_id=job.id,
                    reason=exception_reason,
                )

            else:
                # Proceed to NCB submission queue
                if needs_review:
                    await self.queue_service.update_job_status(
                        job.id,
                        JobStatus.EXTRACTED,
                        needs_review=True,
                        exception_reason=exception_reason,
                    )
                    logger.info(
                        "Job queued for submission with review flag",
                        job_id=job.id,
                        confidence=confidence,
                        review_reason=exception_reason or "Medium confidence",
                    )
                else:
                    logger.info(
                        "High confidence extraction, queuing for automatic submission",
                        job_id=job.id,
                        confidence=confidence,
                    )

                # Re-fetch job with updated metadata
                job = await self.queue_service.get_job(job.id)
                await self.queue_service.enqueue_job(
                    job, queue_name=settings.redis.submission_queue
                )

            # Cleanup temp file
            if image_path.exists():
                image_path.unlink()

            logger.info(
                "Job processing complete",
                job_id=job.id,
                confidence=confidence,
                status=job.status,
            )

        except Exception as e:
            logger.error("Job processing failed", job_id=job.id, error=str(e))
            await self.queue_service.update_job_status(
                job.id, JobStatus.FAILED, error_message=str(e)
            )


async def main():
    """Entry point for OCR processor worker."""
    worker = OCRProcessorWorker()
    try:
        await worker.run()
    except KeyboardInterrupt:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
