"""NCB JSON file generator worker (production mode without NCB API)."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from src.config.settings import settings
from src.models.job import JobStatus
from src.services.queue_service import QueueService
from src.services.sheets_service import SheetsService
from src.services.drive_service import DriveService
from src.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


class NCBJSONGeneratorWorker:
    """
    NCB JSON generator worker.

    Generates NCB-compliant JSON files for manual submission:
    - Pulls jobs from submission queue
    - Builds NCB request payload
    - Saves JSON file to pending directory (local backup)
    - Uploads JSON file to Google Drive (cloud backup)
    - Updates job status
    - Updates Sheets with Drive link
    """

    def __init__(self) -> None:
        """Initialize worker."""
        self.queue_service = QueueService()
        self.sheets_service = SheetsService()
        self.drive_service = DriveService()
        self.running = False

        # JSON output directory
        self.output_dir = Path(getattr(settings, 'ncb_json_output_dir', '/app/data/ncb_pending'))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "NCB JSON generator worker initialized",
            output_dir=str(self.output_dir)
        )

    async def run(self) -> None:
        """Main worker loop."""
        self.running = True
        await self.queue_service.connect()

        logger.info("NCB JSON generator worker started")

        while self.running:
            try:
                # Dequeue job from submission queue
                job = await self.queue_service.dequeue_job(
                    settings.redis.submission_queue, timeout=1
                )

                if job:
                    await self._generate_json(job)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
                break
            except Exception as e:
                logger.error("JSON generation error", error=str(e))
                await asyncio.sleep(1)

        await self.queue_service.disconnect()
        logger.info("NCB JSON generator worker stopped")

    async def stop(self) -> None:
        """Stop worker gracefully."""
        logger.info("Stopping NCB JSON generator worker...")
        self.running = False

    async def _generate_json(self, job) -> None:
        """
        Generate NCB JSON file for a job.

        Steps:
        1. Build NCB request payload
        2. Save JSON file locally
        3. Upload JSON file to Google Drive
        4. Update job status
        5. Update Sheets with Drive link
        """
        logger.info(
            "Generating NCB JSON file",
            job_id=job.id,
            member_id=job.extraction_result.claim.member_id if job.extraction_result else None,
        )

        try:
            # Validate required fields
            if not job.extraction_result:
                logger.error("No extraction result", job_id=job.id)
                await self.queue_service.update_job_status(
                    job.id, JobStatus.FAILED, error="No extraction result"
                )
                return

            claim = job.extraction_result.claim
            if not claim.total_amount or not claim.service_date:
                logger.error(
                    "Missing required fields for NCB JSON",
                    job_id=job.id,
                )
                await self.queue_service.update_job_status(
                    job.id,
                    JobStatus.EXCEPTION,
                    error="Missing required fields (amount or service_date)",
                )
                return

            # Build NCB JSON payload
            service_date_str = (
                claim.service_date.strftime("%Y-%m-%d")
                if isinstance(claim.service_date, datetime)
                else str(claim.service_date)
            )

            # Use policy_number if available, fallback to member_id
            policy_number = claim.policy_number or claim.member_id

            ncb_json = {
                "Event date": service_date_str,
                "Submission Date": datetime.now().isoformat(),
                "Claim Amount": float(claim.total_amount),
                "Invoice Number": claim.receipt_number or "MISSING",
                "Policy Number": policy_number or "MISSING",
                # Metadata for tracking
                "source_email_id": job.email_id,
                "source_filename": job.attachment_filename,
                "extraction_confidence": job.extraction_result.confidence_score,
                "confidence_level": job.extraction_result.confidence_level.value,
                "job_id": job.id,
                "generated_at": datetime.now().isoformat(),
            }

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ncb_claim_{timestamp}_{job.id[:8]}.json"
            filepath = self.output_dir / filename

            # Save JSON file locally
            with open(filepath, "w") as f:
                json.dump(ncb_json, f, indent=2)

            logger.info(
                "NCB JSON file generated locally",
                job_id=job.id,
                filename=filename,
                amount=claim.total_amount,
                confidence=job.extraction_result.confidence_score,
            )

            # Upload JSON file to Google Drive for backup
            drive_file_id = None
            drive_url = None
            try:
                drive_file_id = await self.drive_service.archive_attachment(
                    filepath,
                    job.email_id or job.id,  # Use email_id or job_id as identifier
                    filename
                )
                drive_url = await self.drive_service.get_file_url(drive_file_id)

                logger.info(
                    "NCB JSON file uploaded to Google Drive",
                    job_id=job.id,
                    filename=filename,
                    drive_file_id=drive_file_id,
                    drive_url=drive_url,
                )
            except Exception as e:
                logger.warning(
                    "Failed to upload JSON to Google Drive (local file still available)",
                    job_id=job.id,
                    filename=filename,
                    error=str(e)
                )
                # Continue processing - local file is still valid

            # Update job status
            await self.queue_service.update_job_status(
                job.id,
                JobStatus.SUBMITTED,  # Mark as "submitted" (to JSON file)
                ncb_reference=filename,  # Store filename as reference
                ncb_submitted_at=datetime.now(),
            )

            # Update Sheets with file reference and Drive link
            if job.sheets_row_ref:
                try:
                    # Update NCB status with Drive link if available
                    ncb_ref = drive_url if drive_url else filename
                    await self.sheets_service.update_ncb_status(
                        job.sheets_row_ref,
                        ncb_ref,  # Drive URL or filename
                        "json_generated",
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to update Sheets",
                        job_id=job.id,
                        error=str(e)
                    )

            logger.info(
                "Job completed - JSON ready for manual NCB submission",
                job_id=job.id,
                json_file=str(filepath),
                drive_url=drive_url or "not_uploaded",
            )

        except Exception as e:
            logger.error(
                "Failed to generate NCB JSON",
                job_id=job.id,
                error=str(e)
            )
            await self.queue_service.update_job_status(
                job.id,
                JobStatus.FAILED,
                error=f"JSON generation failed: {str(e)}",
            )
