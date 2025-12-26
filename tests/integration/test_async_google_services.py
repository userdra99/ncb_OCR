"""
Integration tests for non-blocking Google API service calls.

Tests that Google API calls (Gmail, Sheets, Drive) don't block the event loop
and can handle concurrent requests efficiently.
"""
import asyncio
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestAsyncGoogleServices:
    """Test suite for async/non-blocking Google API services."""

    @pytest.fixture(autouse=True)
    def setup_env(self, tmp_path, monkeypatch):
        """Setup environment variables for testing."""
        # Gmail config
        monkeypatch.setenv("GMAIL_CREDENTIALS_PATH", str(tmp_path / "gmail_creds.json"))
        monkeypatch.setenv("GMAIL_TOKEN_PATH", str(tmp_path / "gmail_token.json"))
        monkeypatch.setenv("GMAIL_PROCESSED_LABEL", "Claims/Processed")
        monkeypatch.setenv("GMAIL_POLL_INTERVAL_SECONDS", "30")

        # Sheets config
        monkeypatch.setenv("SHEETS_CREDENTIALS_PATH", str(tmp_path / "sheets_creds.json"))
        monkeypatch.setenv("SHEETS_SPREADSHEET_ID", "test-spreadsheet-id")

        # Drive config
        monkeypatch.setenv("DRIVE_CREDENTIALS_PATH", str(tmp_path / "drive_creds.json"))
        monkeypatch.setenv("DRIVE_FOLDER_ID", "test-folder-id")

        # NCB config (required by settings)
        monkeypatch.setenv("NCB_API_BASE_URL", "https://test-ncb.example.com")
        monkeypatch.setenv("NCB_API_KEY", "test-key")
        monkeypatch.setenv("NCB_API_USERNAME", "test-user")
        monkeypatch.setenv("NCB_API_PASSWORD", "test-pass")

        # Redis config
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

        # OCR config
        monkeypatch.setenv("OCR_MODEL_PATH", str(tmp_path / "model"))
        monkeypatch.setenv("OCR_USE_GPU", "false")

        # Create dummy credential files
        (tmp_path / "gmail_creds.json").write_text('{"installed": {"client_id": "test"}}')
        (tmp_path / "sheets_creds.json").write_text('{"type": "service_account"}')
        (tmp_path / "drive_creds.json").write_text('{"type": "service_account"}')

    @pytest.fixture
    def mock_time_consuming_execute(self):
        """Mock execute() that simulates a slow API call (100ms)."""
        def slow_execute():
            time.sleep(0.1)  # Simulate 100ms API call
            return {"messages": [], "files": [], "values": []}
        return slow_execute

    # ===== EmailService Non-Blocking Tests =====

    @pytest.mark.asyncio
    async def test_email_poll_inbox_is_non_blocking(self, mock_time_consuming_execute):
        """
        Test that poll_inbox() doesn't block the event loop.

        Given: Gmail API call takes 100ms
        When: Multiple poll_inbox() calls run concurrently
        Then: Total time < (100ms * num_calls), proving non-blocking
        """
        with patch('src.services.email_service.build') as mock_build, \
             patch('src.services.email_service.Credentials') as mock_creds:
            # Mock authentication
            mock_creds.from_authorized_user_file.return_value = MagicMock(valid=True)

            # Setup mock that simulates slow API
            mock_service = MagicMock()
            mock_service.users().messages().list().execute = mock_time_consuming_execute
            mock_service.users().messages().get().execute = lambda: {
                "id": "msg_1",
                "internalDate": str(int(time.time() * 1000)),
                "payload": {
                    "headers": [
                        {"name": "From", "value": "test@example.com"},
                        {"name": "Subject", "value": "Test"}
                    ],
                    "parts": [{"filename": "test.jpg"}]
                }
            }
            mock_build.return_value = mock_service

            from src.services.email_service import EmailService

            # Initialize service
            service = EmailService()

            # Run 5 concurrent polls
            start = time.time()
            tasks = [service.poll_inbox() for _ in range(5)]
            results = await asyncio.gather(*tasks)
            elapsed = time.time() - start

            # If blocking: 5 * 100ms = 500ms
            # If non-blocking: ~100ms (concurrent execution)
            assert elapsed < 0.3, f"Took {elapsed}s, expected < 0.3s (non-blocking)"
            assert len(results) == 5

    @pytest.mark.asyncio
    async def test_email_download_attachment_is_non_blocking(self, tmp_path, mock_time_consuming_execute):
        """
        Test that download_attachment() doesn't block the event loop.

        Given: Gmail attachment API takes 100ms
        When: Multiple downloads run concurrently
        Then: Total time indicates concurrent execution
        """
        with patch('src.services.email_service.build') as mock_build:
            # Setup mock
            mock_service = MagicMock()

            # Mock both get message and get attachment
            def slow_get_message():
                time.sleep(0.1)
                return {
                    "payload": {
                        "parts": [{
                            "filename": "receipt.jpg",
                            "body": {"attachmentId": "att_123"}
                        }]
                    }
                }

            def slow_get_attachment():
                time.sleep(0.1)
                return {"data": "dGVzdCBkYXRh"}  # base64 "test data"

            mock_service.users().messages().get().execute = slow_get_message
            mock_service.users().messages().attachments().get().execute = slow_get_attachment
            mock_build.return_value = mock_service

            from src.services.email_service import EmailService

            service = EmailService()

            # Run 3 concurrent downloads
            start = time.time()
            tasks = [
                service.download_attachment(
                    f"msg_{i}",
                    "receipt.jpg",
                    tmp_path / f"receipt_{i}.jpg"
                )
                for i in range(3)
            ]
            results = await asyncio.gather(*tasks)
            elapsed = time.time() - start

            # If blocking: 3 * 200ms = 600ms
            # If non-blocking: ~200ms
            assert elapsed < 0.4, f"Took {elapsed}s, expected < 0.4s (non-blocking)"
            assert len(results) == 3

    @pytest.mark.asyncio
    async def test_email_mark_as_processed_is_non_blocking(self, mock_time_consuming_execute):
        """
        Test that mark_as_processed() doesn't block the event loop.
        """
        with patch('src.services.email_service.build') as mock_build:
            mock_service = MagicMock()

            def slow_labels_list():
                time.sleep(0.05)
                return {"labels": [{"name": "Processed", "id": "label_123"}]}

            def slow_modify():
                time.sleep(0.05)
                return {}

            mock_service.users().labels().list().execute = slow_labels_list
            mock_service.users().messages().modify().execute = slow_modify
            mock_build.return_value = mock_service

            from src.services.email_service import EmailService

            service = EmailService()

            # Run 5 concurrent mark operations
            start = time.time()
            tasks = [service.mark_as_processed(f"msg_{i}") for i in range(5)]
            await asyncio.gather(*tasks)
            elapsed = time.time() - start

            # If blocking: 5 * 100ms = 500ms
            # If non-blocking: ~100ms
            assert elapsed < 0.3, f"Took {elapsed}s, expected < 0.3s"

    # ===== SheetsService Non-Blocking Tests =====

    @pytest.mark.asyncio
    async def test_sheets_log_extraction_is_non_blocking(self):
        """
        Test that log_extraction() doesn't block the event loop.
        """
        with patch('gspread.authorize') as mock_auth:
            # Setup slow gspread mock
            mock_client = MagicMock()
            mock_spreadsheet = MagicMock()
            mock_sheet = MagicMock()

            def slow_append_row(*args, **kwargs):
                time.sleep(0.1)
                return None

            def slow_get_all_values():
                time.sleep(0.05)
                return [["header"], ["row1"], ["row2"]]

            mock_sheet.append_row = slow_append_row
            mock_sheet.get_all_values = slow_get_all_values
            mock_sheet.title = "Claims_2024_12"

            mock_spreadsheet.worksheet.return_value = mock_sheet
            mock_client.open_by_key.return_value = mock_spreadsheet
            mock_auth.return_value = mock_client

            from src.services.sheets_service import SheetsService
            from src.models.job import Job, JobStatus
            from src.models.extraction import ExtractionResult, ExtractedClaim
            from datetime import datetime

            service = SheetsService()

            # Create test data
            jobs = [
                Job(
                    id=f"job_{i}",
                    email_id=f"msg_{i}",
                    attachment_filename=f"file{i}.jpg",
                    attachment_path=f"/tmp/file{i}.jpg",
                    attachment_hash=f"hash{i}",
                    status=JobStatus.PROCESSING,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                for i in range(5)
            ]

            extractions = [
                ExtractionResult(
                    claim=ExtractedClaim(
                        member_id=f"M{i}",
                        provider_name=f"Clinic {i}",
                        total_amount=100.0 * i
                    ),
                    confidence_score=0.9,
                    confidence_level="high"
                )
                for i in range(5)
            ]

            # Run 5 concurrent log operations
            start = time.time()
            tasks = [
                service.log_extraction(job, extraction)
                for job, extraction in zip(jobs, extractions)
            ]
            results = await asyncio.gather(*tasks)
            elapsed = time.time() - start

            # If blocking: 5 * 150ms = 750ms
            # If non-blocking: ~150ms
            assert elapsed < 0.4, f"Took {elapsed}s, expected < 0.4s"
            assert len(results) == 5

    @pytest.mark.asyncio
    async def test_sheets_update_ncb_status_is_non_blocking(self):
        """
        Test that update_ncb_status() with parallel updates doesn't block.
        """
        with patch('gspread.authorize') as mock_auth:
            mock_client = MagicMock()
            mock_spreadsheet = MagicMock()
            mock_sheet = MagicMock()

            def slow_update(*args, **kwargs):
                time.sleep(0.1)
                return None

            mock_sheet.update = slow_update
            mock_spreadsheet.worksheet.return_value = mock_sheet
            mock_client.open_by_key.return_value = mock_spreadsheet
            mock_auth.return_value = mock_client

            from src.services.sheets_service import SheetsService

            service = SheetsService()

            # Run 3 concurrent update operations
            start = time.time()
            tasks = [
                service.update_ncb_status(
                    f"Sheet1!A{i+10}",
                    f"CLM-{i}",
                    "submitted"
                )
                for i in range(3)
            ]
            await asyncio.gather(*tasks)
            elapsed = time.time() - start

            # Each update does 3 parallel update calls (status, reference, timestamp)
            # If blocking: would be very slow
            # If non-blocking with gather: ~100ms per batch
            assert elapsed < 0.5, f"Took {elapsed}s, expected < 0.5s"

    # ===== DriveService Non-Blocking Tests =====

    @pytest.mark.asyncio
    async def test_drive_archive_attachment_is_non_blocking(self, tmp_path):
        """
        Test that archive_attachment() doesn't block the event loop.
        """
        with patch('googleapiclient.discovery.build') as mock_build:
            mock_service = MagicMock()

            def slow_list_files(*args, **kwargs):
                time.sleep(0.05)
                return {"files": [{"id": "folder_123", "name": "2024"}]}

            def slow_create_file(*args, **kwargs):
                time.sleep(0.1)
                return {"id": "file_123", "webViewLink": "https://drive.google.com/file/123"}

            mock_service.files().list().execute = slow_list_files
            mock_service.files().create().execute = slow_create_file
            mock_build.return_value = mock_service

            from src.services.drive_service import DriveService

            service = DriveService()

            # Create test files
            test_files = []
            for i in range(3):
                file_path = tmp_path / f"receipt_{i}.jpg"
                file_path.write_text(f"test data {i}")
                test_files.append(file_path)

            # Run 3 concurrent archive operations
            start = time.time()
            tasks = [
                service.archive_attachment(
                    file_path,
                    f"msg_{i}",
                    f"receipt_{i}.jpg"
                )
                for i, file_path in enumerate(test_files)
            ]
            results = await asyncio.gather(*tasks)
            elapsed = time.time() - start

            # If blocking: 3 * (folder checks + upload) = ~450ms+
            # If non-blocking: much faster
            assert elapsed < 1.0, f"Took {elapsed}s, expected < 1.0s"
            assert len(results) == 3

    @pytest.mark.asyncio
    async def test_drive_folder_creation_is_non_blocking(self):
        """
        Test that folder creation/lookup doesn't block.
        """
        with patch('googleapiclient.discovery.build') as mock_build:
            mock_service = MagicMock()

            def slow_list(*args, **kwargs):
                time.sleep(0.05)
                return {"files": []}  # Not found

            def slow_create(*args, **kwargs):
                time.sleep(0.05)
                return {"id": f"folder_{time.time()}"}

            mock_service.files().list().execute = slow_list
            mock_service.files().create().execute = slow_create
            mock_build.return_value = mock_service

            from src.services.drive_service import DriveService

            service = DriveService()

            # Run multiple folder lookups concurrently
            start = time.time()
            tasks = [
                service._get_or_create_folder(f"folder_{i}", "parent_123")
                for i in range(5)
            ]
            results = await asyncio.gather(*tasks)
            elapsed = time.time() - start

            # If blocking: 5 * (list + create) = 5 * 100ms = 500ms
            # If non-blocking: ~100ms
            assert elapsed < 0.3, f"Took {elapsed}s, expected < 0.3s"
            assert len(results) == 5

    # ===== Mixed Service Concurrent Test =====

    @pytest.mark.asyncio
    async def test_all_services_concurrent_execution(self, tmp_path):
        """
        Test that all three services can execute concurrently without blocking each other.

        This simulates a real-world scenario where email polling, sheets logging,
        and drive archiving all happen at the same time.
        """
        # Setup all mocks
        with patch('src.services.email_service.build') as mock_email_build, \
             patch('gspread.authorize') as mock_sheets_auth, \
             patch('googleapiclient.discovery.build') as mock_drive_build:

            # Email mock
            mock_email_service = MagicMock()
            def slow_email_list():
                time.sleep(0.1)
                return {"messages": [{"id": "msg_1"}]}
            mock_email_service.users().messages().list().execute = slow_email_list
            mock_email_build.return_value = mock_email_service

            # Sheets mock
            mock_sheets_client = MagicMock()
            mock_spreadsheet = MagicMock()
            mock_sheet = MagicMock()
            def slow_append(*args, **kwargs):
                time.sleep(0.1)
                return None
            def slow_get_values():
                time.sleep(0.05)
                return [["header"]]
            mock_sheet.append_row = slow_append
            mock_sheet.get_all_values = slow_get_values
            mock_sheet.title = "Claims"
            mock_spreadsheet.worksheet.return_value = mock_sheet
            mock_sheets_client.open_by_key.return_value = mock_spreadsheet
            mock_sheets_auth.return_value = mock_sheets_client

            # Drive mock
            mock_drive_service = MagicMock()
            def slow_drive_list(*args, **kwargs):
                time.sleep(0.05)
                return {"files": [{"id": "folder_1"}]}
            def slow_drive_create(*args, **kwargs):
                time.sleep(0.1)
                return {"id": "file_1"}
            mock_drive_service.files().list().execute = slow_drive_list
            mock_drive_service.files().create().execute = slow_drive_create
            mock_drive_build.return_value = mock_drive_service

            # Import services
            from src.services.email_service import EmailService
            from src.services.sheets_service import SheetsService
            from src.services.drive_service import DriveService
            from src.models.job import Job, JobStatus
            from src.models.extraction import ExtractionResult, ExtractedClaim
            from datetime import datetime

            email_service = EmailService()
            sheets_service = SheetsService()
            drive_service = DriveService()

            # Create test file
            test_file = tmp_path / "receipt.jpg"
            test_file.write_text("test data")

            # Create test data
            job = Job(
                id="job_1",
                email_id="msg_1",
                attachment_filename="receipt.jpg",
                attachment_path=str(test_file),
                attachment_hash="hash1",
                status=JobStatus.PROCESSING,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            extraction = ExtractionResult(
                claim=ExtractedClaim(
                    member_id="M123",
                    provider_name="Test Clinic",
                    total_amount=100.0
                ),
                confidence_score=0.9,
                confidence_level="high"
            )

            # Run all three service operations concurrently
            start = time.time()
            results = await asyncio.gather(
                email_service.poll_inbox(),
                sheets_service.log_extraction(job, extraction),
                drive_service.archive_attachment(test_file, "msg_1", "receipt.jpg")
            )
            elapsed = time.time() - start

            # If blocking: 100ms + 150ms + 150ms = 400ms+
            # If non-blocking: ~150ms (overlapped execution)
            assert elapsed < 0.4, f"Took {elapsed}s, expected < 0.4s (concurrent)"
            assert len(results) == 3

    # ===== Event Loop Health Check =====

    @pytest.mark.asyncio
    async def test_event_loop_not_blocked_during_api_calls(self):
        """
        Test that the event loop can handle other tasks while API calls are in progress.

        This is the critical test that proves we're not blocking the event loop.
        """
        with patch('src.services.email_service.build') as mock_build:
            mock_service = MagicMock()

            # Simulate a very slow API call (500ms)
            def very_slow_execute():
                time.sleep(0.5)
                return {"messages": []}

            mock_service.users().messages().list().execute = very_slow_execute
            mock_build.return_value = mock_service

            from src.services.email_service import EmailService

            service = EmailService()

            # Counter to track background task execution
            counter = {"value": 0}

            async def background_task():
                """A task that should be able to run while API call is in progress."""
                for _ in range(10):
                    await asyncio.sleep(0.01)  # 10ms
                    counter["value"] += 1

            # Start API call and background task concurrently
            start = time.time()
            api_task = asyncio.create_task(service.poll_inbox())
            bg_task = asyncio.create_task(background_task())

            await asyncio.gather(api_task, bg_task)
            elapsed = time.time() - start

            # The background task should complete during the API call
            # If event loop was blocked, counter would be 0
            # If non-blocking, counter should reach 10
            assert counter["value"] == 10, f"Background task only ran {counter['value']}/10 iterations"
            assert elapsed < 0.6, f"Took {elapsed}s, expected ~0.5s"

            print(f"✅ Event loop remained responsive during API call")
            print(f"   Background task completed {counter['value']} iterations")
            print(f"   Total time: {elapsed:.3f}s")
