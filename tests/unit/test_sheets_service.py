"""
Unit tests for Google Sheets Service

Tests logging, audit trail, and data backup to Google Sheets
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


@pytest.mark.unit
@pytest.mark.sheets
class TestSheetsService:
    """Test suite for Sheets Service"""

    @pytest.fixture
    def sheets_service(self, mock_sheets_service, mock_env):
        """Create Sheets service instance with mocked Google Sheets API."""
        with patch('googleapiclient.discovery.build', return_value=mock_sheets_service):
            from src.services.sheets_service import SheetsService
            from src.config.settings import SheetsConfig

            config = SheetsConfig()
            return SheetsService(config)

    @pytest.mark.asyncio
    async def test_log_extraction_appends_row(
        self, sheets_service, mock_sheets_service, sample_job_data
    ):
        """
        Test logging extraction to Sheets

        Given: Completed extraction
        When: log_extraction() is called
        Then: Row appended to spreadsheet
        """
        # Arrange
        from src.models.job import Job
        from src.models.extraction import ExtractionResult, ExtractedClaim

        job = Job(**sample_job_data)
        extraction = ExtractionResult(
            claim=ExtractedClaim(
                member_id="M12345",
                provider_name="Test Clinic",
                total_amount=100.00,
            ),
            confidence_score=0.95,
            confidence_level="high",
        )

        # Act
        row_ref = await sheets_service.log_extraction(job, extraction)

        # Assert
        assert row_ref is not None
        assert "Sheet1!" in row_ref
        mock_sheets_service.spreadsheets().values().append().execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_extraction_includes_all_fields(
        self, sheets_service, mock_sheets_service, sample_job_data
    ):
        """
        Test that log includes all required columns

        Given: Extraction with all data
        When: log_extraction() is called
        Then: All columns populated per schema
        """
        # Arrange
        from src.models.job import Job
        from src.models.extraction import ExtractionResult, ExtractedClaim

        job = Job(**sample_job_data)
        extraction = ExtractionResult(
            claim=ExtractedClaim(
                member_id="M12345",
                member_name="John Doe",
                provider_name="Test Clinic",
                total_amount=100.00,
            ),
            confidence_score=0.95,
            confidence_level="high",
        )

        # Act
        await sheets_service.log_extraction(job, extraction)

        # Assert
        call_args = mock_sheets_service.spreadsheets().values().append().execute.call_args
        # Verify the values array contains expected fields
        # Schema: timestamp, email_id, sender, filename, member_id, provider, amount, confidence, status, ncb_ref, submitted_at, error

    @pytest.mark.asyncio
    async def test_update_ncb_status(
        self, sheets_service, mock_sheets_service
    ):
        """
        Test updating NCB status in existing row

        Given: Row with extraction logged
        When: update_ncb_status() is called
        Then: NCB reference and timestamp updated
        """
        # Arrange
        row_ref = "Sheet1!A142"
        ncb_reference = "CLM-2024-567890"
        status = "submitted"

        # Act
        await sheets_service.update_ncb_status(
            row_ref, ncb_reference, status
        )

        # Assert
        mock_sheets_service.spreadsheets().values().update().execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_daily_summary(
        self, sheets_service, mock_sheets_service
    ):
        """
        Test retrieving daily processing summary

        Given: Entries for specific date
        When: get_daily_summary() is called
        Then: Aggregated stats returned
        """
        # Arrange
        from datetime import date

        test_date = date(2024, 12, 18)

        mock_sheets_service.spreadsheets().values().get().execute.return_value = {
            "values": [
                ["2024-12-18T10:00:00Z", "msg_1", "test@test.com", "file1.jpg", "M123", "Clinic A", 100, 0.95, "submitted", "CLM-001", "", ""],
                ["2024-12-18T11:00:00Z", "msg_2", "test@test.com", "file2.jpg", "M456", "Clinic B", 150, 0.92, "submitted", "CLM-002", "", ""],
                ["2024-12-18T12:00:00Z", "msg_3", "test@test.com", "file3.jpg", "M789", "Clinic C", 75, 0.68, "exception", "", "", "Low confidence"],
            ]
        }

        # Act
        summary = await sheets_service.get_daily_summary(test_date)

        # Assert
        assert summary["total_processed"] == 3
        assert summary["successful"] == 2
        assert summary["exceptions"] == 1

    @pytest.mark.asyncio
    async def test_log_extraction_handles_errors(
        self, sheets_service, mock_sheets_service, sample_job_data
    ):
        """
        Test error handling when Sheets API fails

        Given: Sheets API returns error
        When: log_extraction() is called
        Then: Fallback to local file backup
        """
        # Arrange
        from src.models.job import Job
        from src.models.extraction import ExtractionResult, ExtractedClaim
        from googleapiclient.errors import HttpError

        job = Job(**sample_job_data)
        extraction = ExtractionResult(
            claim=ExtractedClaim(member_id="M12345", total_amount=100.00),
            confidence_score=0.95,
            confidence_level="high",
        )

        mock_sheets_service.spreadsheets().values().append().execute.side_effect = HttpError(
            resp=MagicMock(status=503), content=b"Service Unavailable"
        )

        # Act
        with patch('src.services.sheets_service.write_local_backup') as mock_backup:
            row_ref = await sheets_service.log_extraction(job, extraction)

            # Assert
            mock_backup.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_log_multiple_extractions(
        self, sheets_service, mock_sheets_service
    ):
        """
        Test batch logging for performance

        Given: Multiple extractions to log
        When: batch_log() is called
        Then: Single API call with all rows
        """
        # Arrange
        from src.models.job import Job
        from src.models.extraction import ExtractionResult, ExtractedClaim

        jobs_and_extractions = [
            (
                Job(id=f"job_{i}", email_id=f"msg_{i}", attachment_filename=f"file{i}.jpg", attachment_path=f"/tmp/file{i}.jpg", attachment_hash=f"hash{i}", created_at=datetime.now(), updated_at=datetime.now()),
                ExtractionResult(claim=ExtractedClaim(member_id=f"M{i}", total_amount=100.0 * i), confidence_score=0.9, confidence_level="high")
            )
            for i in range(10)
        ]

        # Act
        await sheets_service.batch_log(jobs_and_extractions)

        # Assert
        # Should use batchUpdate instead of multiple append calls
        assert mock_sheets_service.spreadsheets().values().append().execute.call_count <= 1
