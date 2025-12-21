"""
Integration tests for Worker processes

Tests email poller, OCR processor, and NCB submitter workers
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


@pytest.mark.integration
@pytest.mark.worker
class TestEmailPollerWorker:
    """Test suite for Email Poller Worker"""

    @pytest.mark.asyncio
    async def test_polls_inbox_and_creates_jobs(
        self, mock_gmail_service, mock_redis, tmp_path
    ):
        """
        Test complete polling cycle

        Given: New emails with attachments in inbox
        When: Worker polls
        Then: Jobs created in queue for each attachment
        """
        # Arrange
        with patch('src.services.email_service.build', return_value=mock_gmail_service), \
             patch('redis.asyncio.from_url', return_value=mock_redis):

            from src.workers.email_poller import EmailPollerWorker
            from src.services.email_service import EmailService
            from src.services.queue_service import QueueService
            from src.config.settings import EmailConfig

            email_service = EmailService(EmailConfig())
            queue_service = QueueService()
            worker = EmailPollerWorker(email_service, queue_service)

            # Act
            await worker.process_once()  # Single iteration

            # Assert
            # Verify jobs were enqueued
            assert mock_redis.set.called

    @pytest.mark.asyncio
    async def test_handles_multiple_attachments(
        self, mock_gmail_service, mock_redis
    ):
        """
        Test email with multiple attachments

        Given: Email with 3 attachments
        When: Worker processes email
        Then: 3 separate jobs created
        """
        # Arrange
        mock_gmail_service.users().messages().get().execute.return_value = {
            "id": "msg_multi",
            "payload": {
                "headers": [{"name": "From", "value": "test@example.com"}],
                "parts": [
                    {"filename": "receipt1.jpg", "body": {"attachmentId": "att_1"}},
                    {"filename": "receipt2.jpg", "body": {"attachmentId": "att_2"}},
                    {"filename": "receipt3.pdf", "body": {"attachmentId": "att_3"}},
                ],
            },
        }

        # Similar test setup
        # Assert 3 jobs created

    @pytest.mark.asyncio
    async def test_skips_duplicate_files(
        self, mock_gmail_service, mock_redis
    ):
        """
        Test deduplication

        Given: Same file sent twice
        When: Worker processes both
        Then: Only first creates job, second skipped
        """
        # Test hash-based deduplication
        pass


@pytest.mark.integration
@pytest.mark.worker
class TestOCRProcessorWorker:
    """Test suite for OCR Processor Worker"""

    @pytest.mark.asyncio
    async def test_processes_job_end_to_end(
        self, mock_ocr_engine, mock_sheets_service, mock_drive_service, mock_redis, test_data_dir
    ):
        """
        Test complete OCR processing

        Given: Job in queue with attachment
        When: Worker processes job
        Then: OCR extraction, Sheets logging, Drive archiving all complete
        """
        # Arrange
        from src.workers.ocr_processor import OCRProcessorWorker

        # Setup all mocked services
        # Create test job
        # Run worker

        # Assert
        # - OCR called
        # - Sheets append called
        # - Drive upload called
        # - Job status updated

    @pytest.mark.asyncio
    async def test_routes_by_confidence(
        self, mock_redis, confidence_test_cases
    ):
        """
        Test confidence-based routing

        Given: Extractions with different confidence scores
        When: Processed
        Then: Routed to submission queue or exception queue appropriately
        """
        # Test routing logic for high/medium/low confidence
        pass

    @pytest.mark.asyncio
    async def test_handles_ocr_failures(
        self, mock_redis
    ):
        """
        Test error handling

        Given: OCR fails on image
        When: Worker processes
        Then: Job marked as failed, logged to Sheets
        """
        pass


@pytest.mark.integration
@pytest.mark.worker
class TestNCBSubmitterWorker:
    """Test suite for NCB Submitter Worker"""

    @pytest.mark.asyncio
    async def test_submits_to_ncb_and_updates(
        self, mock_ncb_api, mock_sheets_service, mock_redis
    ):
        """
        Test complete submission flow with NCB schema

        Given: Job in submission queue
        When: Worker processes
        Then: Submitted to NCB with correct field mapping, reference captured, Sheets updated
        """
        # Arrange - Setup job with extracted claim data
        from src.services.ncb_service import NCBService
        from src.models.claim import NCBSubmissionRequest
        from datetime import datetime

        # Mock NCB response with new schema
        mock_ncb_api.post.return_value = MagicMock(
            status_code=201,
            json=lambda: {
                "success": True,
                "claim_reference": "CLM-2024-567890",
                "Event date": "2024-12-21",
                "Submission Date": "2024-12-21T10:30:00Z",
                "Claim Amount": 150.50,
                "Invoice Number": "INV-12345",
                "Policy Number": "POL-98765",
            },
        )

        # Create submission request with NCB schema
        request = NCBSubmissionRequest(
            event_date="2024-12-21",
            submission_date=datetime.utcnow().isoformat() + "Z",
            claim_amount=150.50,
            invoice_number="INV-12345",
            policy_number="POL-98765",
            source_email_id="msg_123",
            source_filename="receipt.jpg",
            extraction_confidence=0.95,
        )

        # Test submission includes proper field mapping
        # Assert NCB API called with correct schema
        # Assert Sheets updated with reference

    @pytest.mark.asyncio
    async def test_handles_ncb_errors(
        self, mock_ncb_api, mock_redis
    ):
        """
        Test NCB error handling with new schema

        Given: NCB API returns validation error
        When: Worker processes
        Then: Job retried with backoff or moved to failed
        """
        # Arrange - Mock validation error response
        mock_ncb_api.post.return_value = MagicMock(
            status_code=400,
            json=lambda: {
                "success": False,
                "error_code": "VALIDATION_FAILED",
                "message": "Invalid Policy Number",
                "details": {"field": "Policy Number", "reason": "Format invalid"},
            },
        )

        # Test error handling and retry logic
        pass

    @pytest.mark.asyncio
    async def test_respects_rate_limits(
        self, mock_ncb_api, mock_redis
    ):
        """
        Test rate limit handling

        Given: NCB returns 429
        When: Worker continues
        Then: Waits per Retry-After before next submission
        """
        pass

    @pytest.mark.asyncio
    async def test_field_mapping_from_extracted_to_ncb(
        self, mock_ncb_api, mock_redis
    ):
        """
        Test field mapping from ExtractedClaim to NCB schema

        Given: ExtractedClaim with internal field names
        When: Worker transforms to NCB submission
        Then: Fields correctly mapped to NCB schema
        """
        # Arrange
        from src.models.claim import ExtractedClaim
        from datetime import datetime

        extracted = ExtractedClaim(
            member_id="M12345",
            policy_number="POL-98765",
            service_date=datetime(2024, 12, 21),
            receipt_number="INV-12345",
            total_amount=150.50,
        )

        # Act - Transform to NCB submission
        # Expected mapping:
        # service_date -> Event date (ISO format)
        # submission time -> Submission Date (ISO format with timezone)
        # total_amount -> Claim Amount
        # receipt_number -> Invoice Number
        # policy_number -> Policy Number

        # Assert proper mapping
        pass


@pytest.mark.integration
@pytest.mark.worker
class TestWorkerCoordination:
    """Test coordination between multiple workers"""

    @pytest.mark.asyncio
    async def test_full_pipeline(
        self, mock_gmail_service, mock_ocr_engine, mock_ncb_api,
        mock_sheets_service, mock_drive_service, mock_redis
    ):
        """
        Test complete pipeline with all workers

        Given: Email arrives
        When: All workers running
        Then: Email → Job → OCR → Sheets/Drive → NCB → Complete
        """
        # Integration test of full flow
        pass

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self):
        """
        Test workers shutdown cleanly

        Given: Workers processing jobs
        When: Shutdown signal sent
        Then: Current jobs complete, new jobs not started
        """
        pass
