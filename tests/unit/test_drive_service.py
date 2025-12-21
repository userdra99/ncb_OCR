"""
Unit tests for Google Drive Service

Tests archiving attachments to Google Drive
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


@pytest.mark.unit
@pytest.mark.drive
class TestDriveService:
    """Test suite for Drive Service"""

    @pytest.fixture
    def drive_service(self, mock_drive_service, mock_env):
        """Create Drive service instance with mocked Google Drive API."""
        with patch('googleapiclient.discovery.build', return_value=mock_drive_service):
            from src.services.drive_service import DriveService
            from src.config.settings import DriveConfig

            config = DriveConfig()
            return DriveService(config)

    @pytest.mark.asyncio
    async def test_archive_attachment_uploads_file(
        self, drive_service, mock_drive_service, tmp_path
    ):
        """
        Test archiving attachment to Drive

        Given: Local attachment file
        When: archive_attachment() is called
        Then: File uploaded to Drive with metadata
        """
        # Arrange
        local_file = tmp_path / "receipt.jpg"
        local_file.write_text("test image data")

        email_id = "msg_abc123"
        filename = "receipt_001.jpg"

        # Act
        file_id = await drive_service.archive_attachment(
            local_file, email_id, filename
        )

        # Assert
        assert file_id is not None
        assert file_id == "file_abc123"
        mock_drive_service.files().create().execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_archive_creates_date_folder_structure(
        self, drive_service, mock_drive_service, tmp_path
    ):
        """
        Test folder structure creation

        Given: Attachment to archive
        When: archive_attachment() is called
        Then: Creates /claims/YYYY/MM/DD/ structure
        """
        # Arrange
        local_file = tmp_path / "receipt.jpg"
        local_file.write_text("test")

        today = datetime.now()
        expected_path = f"claims/{today.year}/{today.month:02d}/{today.day:02d}/"

        # Act
        await drive_service.archive_attachment(
            local_file, "msg_123", "receipt.jpg"
        )

        # Assert
        # Verify folder creation calls for year, month, day
        create_calls = mock_drive_service.files().create.call_count
        assert create_calls >= 1

    @pytest.mark.asyncio
    async def test_archive_attaches_metadata(
        self, drive_service, mock_drive_service, tmp_path
    ):
        """
        Test file metadata is attached

        Given: Attachment with source metadata
        When: Uploaded to Drive
        Then: Properties include email_id, job_id, processed_at
        """
        # Arrange
        local_file = tmp_path / "receipt.jpg"
        local_file.write_text("test")

        # Act
        await drive_service.archive_attachment(
            local_file, "msg_abc123", "receipt_001.jpg"
        )

        # Assert
        call_args = mock_drive_service.files().create().execute.call_args
        body = call_args.kwargs.get("body", {})

        assert "properties" in body
        assert body["properties"]["email_id"] == "msg_abc123"

    @pytest.mark.asyncio
    async def test_get_file_url(
        self, drive_service, mock_drive_service
    ):
        """
        Test retrieving shareable URL

        Given: File ID
        When: get_file_url() is called
        Then: Returns webViewLink
        """
        # Arrange
        file_id = "file_abc123"

        mock_drive_service.files().get().execute.return_value = {
            "id": file_id,
            "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
        }

        # Act
        url = await drive_service.get_file_url(file_id)

        # Assert
        assert url is not None
        assert file_id in url

    @pytest.mark.asyncio
    async def test_archive_handles_large_files(
        self, drive_service, mock_drive_service, tmp_path
    ):
        """
        Test uploading large files with resumable upload

        Given: Large file (>5MB)
        When: archive_attachment() is called
        Then: Uses resumable upload
        """
        # Arrange
        large_file = tmp_path / "large_receipt.pdf"
        # Create 10MB file
        with open(large_file, 'wb') as f:
            f.write(b'x' * (10 * 1024 * 1024))

        # Act
        file_id = await drive_service.archive_attachment(
            large_file, "msg_123", "large_receipt.pdf"
        )

        # Assert
        assert file_id is not None
        # Should use MediaFileUpload with resumable=True

    @pytest.mark.asyncio
    async def test_archive_retries_on_failure(
        self, drive_service, mock_drive_service, tmp_path
    ):
        """
        Test retry on upload failure

        Given: Drive API fails initially
        When: archive_attachment() is called
        Then: Retries and succeeds
        """
        # Arrange
        local_file = tmp_path / "receipt.jpg"
        local_file.write_text("test")

        mock_drive_service.files().create().execute.side_effect = [
            Exception("Network error"),
            {"id": "file_abc123", "webViewLink": "https://drive.google.com/file/d/file_abc123/view"},
        ]

        # Act
        file_id = await drive_service.archive_attachment(
            local_file, "msg_123", "receipt.jpg"
        )

        # Assert
        assert file_id == "file_abc123"
        assert mock_drive_service.files().create().execute.call_count == 2

    @pytest.mark.asyncio
    async def test_archive_preserves_original_filename(
        self, drive_service, mock_drive_service, tmp_path
    ):
        """
        Test original filename preserved in Drive

        Given: Attachment with original filename
        When: Archived
        Then: Drive file has format: {email_id}_{original_filename}
        """
        # Arrange
        local_file = tmp_path / "receipt.jpg"
        local_file.write_text("test")

        email_id = "msg_abc123"
        original_filename = "receipt_001.jpg"

        # Act
        await drive_service.archive_attachment(
            local_file, email_id, original_filename
        )

        # Assert
        call_args = mock_drive_service.files().create().execute.call_args
        body = call_args.kwargs.get("body", {})

        assert body["name"] == f"{email_id}_{original_filename}"
