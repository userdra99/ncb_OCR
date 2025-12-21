"""Email poller worker for monitoring inbox."""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path

from src.config.settings import settings
from src.models.job import Job, JobStatus
from src.services.email_service import EmailService
from src.services.queue_service import QueueService
from src.utils.deduplication import compute_file_hash
from src.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


class EmailPollerWorker:
    """
    Email poller worker.

    Monitors Gmail inbox for new claim emails with attachments.
    Creates jobs for each attachment and enqueues for processing.
    """

    def __init__(self) -> None:
        """Initialize worker."""
        self.email_service = EmailService()
        self.queue_service = QueueService()
        self.temp_dir = settings.storage.temp_storage_path
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.poll_interval = settings.gmail.poll_interval_seconds
        self.running = False
        logger.info("Email poller worker initialized")

    async def run(self) -> None:
        """Main worker loop."""
        self.running = True
        await self.queue_service.connect()

        logger.info("Email poller worker started", poll_interval=self.poll_interval)

        while self.running:
            try:
                await self._poll_cycle()
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
                break
            except Exception as e:
                logger.error("Polling cycle error", error=str(e))

            # Wait before next poll
            await asyncio.sleep(self.poll_interval)

        await self.queue_service.disconnect()
        logger.info("Email poller worker stopped")

    async def stop(self) -> None:
        """Stop worker gracefully."""
        logger.info("Stopping email poller worker...")
        self.running = False

    async def _poll_cycle(self) -> None:
        """Single polling cycle."""
        try:
            # Poll inbox
            emails = await self.email_service.poll_inbox()

            if not emails:
                logger.debug("No new emails found")
                return

            logger.info("Found new emails", count=len(emails))

            # Process each email
            for email in emails:
                try:
                    await self._process_email(email)
                except Exception as e:
                    logger.error(
                        "Failed to process email",
                        email_id=email.message_id,
                        error=str(e),
                    )

        except Exception as e:
            logger.error("Polling error", error=str(e))
            raise

    async def _process_email(self, email) -> None:
        """
        Process single email.

        Steps:
        1. Download attachments
        2. Compute hashes
        3. Check for duplicates
        4. Create jobs
        5. Mark email processed
        """
        logger.info(
            "Processing email",
            email_id=email.message_id,
            sender=email.sender,
            attachments=len(email.attachments),
        )

        processed_count = 0

        for attachment_filename in email.attachments:
            try:
                # Download attachment
                destination = self.temp_dir / f"{email.message_id}_{attachment_filename}"
                await self.email_service.download_attachment(
                    email.message_id, attachment_filename, destination
                )

                # Compute hash
                file_hash = compute_file_hash(destination)

                # Check for duplicate
                is_duplicate = await self.queue_service.check_duplicate(file_hash)
                if is_duplicate:
                    logger.info(
                        "Duplicate attachment detected, skipping",
                        email_id=email.message_id,
                        filename=attachment_filename,
                        file_hash=file_hash,
                    )
                    destination.unlink()  # Delete duplicate
                    continue

                # Create job
                job = Job(
                    id=f"job_{uuid.uuid4().hex}",
                    email_id=email.message_id,
                    attachment_filename=attachment_filename,
                    attachment_path=str(destination),
                    attachment_hash=file_hash,
                    status=JobStatus.PENDING,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )

                # Enqueue job
                await self.queue_service.enqueue_job(job)

                # Record hash
                await self.queue_service.record_hash(file_hash, job.id)

                processed_count += 1
                logger.info(
                    "Job created for attachment",
                    job_id=job.id,
                    email_id=email.message_id,
                    filename=attachment_filename,
                )

            except Exception as e:
                logger.error(
                    "Failed to process attachment",
                    email_id=email.message_id,
                    filename=attachment_filename,
                    error=str(e),
                )

        # Mark email as processed if at least one attachment was processed
        if processed_count > 0:
            try:
                await self.email_service.mark_as_processed(email.message_id)
                logger.info(
                    "Email marked as processed",
                    email_id=email.message_id,
                    processed_attachments=processed_count,
                )
            except Exception as e:
                logger.error(
                    "Failed to mark email as processed",
                    email_id=email.message_id,
                    error=str(e),
                )


async def main():
    """Entry point for email poller worker."""
    worker = EmailPollerWorker()
    try:
        await worker.run()
    except KeyboardInterrupt:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
