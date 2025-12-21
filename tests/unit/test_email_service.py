"""
Unit tests for Email Service

Tests Gmail API integration for polling, downloading, and marking emails
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime


@pytest.mark.unit
@pytest.mark.gmail
class TestEmailService:
    """Test suite for Email Service"""

    @pytest.fixture
    def email_service(self, mock_gmail_service, mock_env):
        """Create Email service instance with mocked Gmail API."""
        with patch('src.services.email_service.build', return_value=mock_gmail_service):
            from src.services.email_service import EmailService
            from src.config.settings import EmailConfig

            config = EmailConfig()
            return EmailService(config)

    @pytest.mark.asyncio
    async def test_poll_inbox_returns_emails_with_attachments(
        self, email_service, mock_gmail_service
    ):
        """
        Test polling inbox for emails with attachments

        Given: Inbox with emails containing attachments
        When: poll_inbox() is called
        Then: List of EmailMetadata returned for unread emails with attachments
        """
        # Arrange
        mock_gmail_service.users().messages().list().execute.return_value = {
            "messages": [
                {"id": "msg_001"},
                {"id": "msg_002"},
            ],
            "nextPageToken": None,
        }

        # Act
        emails = await email_service.poll_inbox()

        # Assert
        assert len(emails) == 2
        assert all(len(email.attachments) > 0 for email in emails)
        assert all(email.message_id is not None for email in emails)

    @pytest.mark.asyncio
    async def test_poll_inbox_filters_already_processed(
        self, email_service, mock_gmail_service
    ):
        """
        Test that already processed emails are filtered out

        Given: Inbox with processed and unprocessed emails
        When: poll_inbox() is called
        Then: Only unprocessed emails returned
        """
        # Arrange - Mock list call to filter by label
        list_mock = mock_gmail_service.users().messages().list

        # Act
        await email_service.poll_inbox()

        # Assert
        # Verify query includes filter for processed label
        call_args = list_mock.call_args
        assert "has:attachment" in call_args.kwargs.get("q", "")
        assert "is:unread" in call_args.kwargs.get("q", "")
        assert "-label:Claims/Processed" in call_args.kwargs.get("q", "") or \
               "-label:" in call_args.kwargs.get("q", "")

    @pytest.mark.asyncio
    async def test_poll_inbox_handles_pagination(
        self, email_service, mock_gmail_service
    ):
        """
        Test pagination when inbox has many emails

        Given: Inbox with more than 50 emails
        When: poll_inbox() is called
        Then: All pages fetched and concatenated
        """
        # Arrange
        mock_gmail_service.users().messages().list().execute.side_effect = [
            {
                "messages": [{"id": f"msg_{i}"} for i in range(50)],
                "nextPageToken": "page_2_token",
            },
            {
                "messages": [{"id": f"msg_{i}"} for i in range(50, 75)],
                "nextPageToken": None,
            },
        ]

        # Act
        emails = await email_service.poll_inbox()

        # Assert
        assert len(emails) == 75

    @pytest.mark.asyncio
    async def test_download_attachment_saves_to_destination(
        self, email_service, mock_gmail_service, tmp_path
    ):
        """
        Test attachment download

        Given: Email with attachment
        When: download_attachment() is called
        Then: Attachment saved to specified path
        """
        # Arrange
        message_id = "msg_123"
        attachment_id = "att_456"
        destination = tmp_path / "receipt.jpg"

        mock_gmail_service.users().messages().attachments().get().execute.return_value = {
            "data": "base64encodeddata=="
        }

        # Act
        result_path = await email_service.download_attachment(
            message_id, attachment_id, destination
        )

        # Assert
        assert result_path == destination
        assert result_path.exists()

    @pytest.mark.asyncio
    async def test_download_attachment_handles_large_files(
        self, email_service, mock_gmail_service, tmp_path
    ):
        """
        Test downloading large attachments

        Given: Email with large attachment (>10MB)
        When: download_attachment() is called
        Then: File downloaded successfully with chunking
        """
        # Arrange
        message_id = "msg_123"
        attachment_id = "att_large"
        destination = tmp_path / "large_receipt.pdf"

        # Mock large file data
        large_data = "x" * (15 * 1024 * 1024)  # 15MB
        mock_gmail_service.users().messages().attachments().get().execute.return_value = {
            "data": large_data
        }

        # Act
        result_path = await email_service.download_attachment(
            message_id, attachment_id, destination
        )

        # Assert
        assert result_path.exists()
        assert result_path.stat().st_size > 10 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_download_attachment_validates_size_limit(
        self, email_service, mock_gmail_service, tmp_path
    ):
        """
        Test attachment size validation

        Given: Attachment exceeding size limit (25MB)
        When: download_attachment() is called
        Then: ValueError raised
        """
        # Arrange
        message_id = "msg_123"
        attachment_id = "att_toolarge"
        destination = tmp_path / "huge_file.pdf"

        # Mock file exceeding limit
        mock_gmail_service.users().messages().attachments().get().execute.return_value = {
            "size": 30 * 1024 * 1024,  # 30MB
            "data": "oversized"
        }

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await email_service.download_attachment(
                message_id, attachment_id, destination
            )

        assert "size" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_mark_as_processed_updates_labels(
        self, email_service, mock_gmail_service
    ):
        """
        Test marking email as processed

        Given: Unprocessed email
        When: mark_as_processed() is called
        Then: Email marked as read and labeled as processed
        """
        # Arrange
        message_id = "msg_123"

        # Act
        await email_service.mark_as_processed(message_id)

        # Assert
        modify_call = mock_gmail_service.users().messages().modify
        modify_call.assert_called_once()

        call_args = modify_call.call_args
        body = call_args.kwargs.get("body", {})

        assert "UNREAD" in body.get("removeLabelIds", [])
        assert any("Processed" in label for label in body.get("addLabelIds", []))

    @pytest.mark.asyncio
    async def test_get_message_body_extracts_plain_text(
        self, email_service, mock_gmail_service
    ):
        """
        Test extracting plain text body from email

        Given: Email with text body
        When: get_message_body() is called
        Then: Plain text body returned
        """
        # Arrange
        message_id = "msg_123"
        expected_body = "Please process the attached medical claim for member M12345."

        mock_gmail_service.users().messages().get().execute.return_value = {
            "payload": {
                "mimeType": "text/plain",
                "body": {
                    "data": expected_body.encode().hex()
                }
            }
        }

        # Act
        body = await email_service.get_message_body(message_id)

        # Assert
        assert expected_body in body

    @pytest.mark.asyncio
    async def test_get_message_body_handles_html(
        self, email_service, mock_gmail_service
    ):
        """
        Test extracting text from HTML email

        Given: Email with HTML body
        When: get_message_body() is called
        Then: HTML converted to plain text
        """
        # Arrange
        message_id = "msg_123"
        html_body = "<html><body><p>Test claim for M12345</p></body></html>"

        mock_gmail_service.users().messages().get().execute.return_value = {
            "payload": {
                "mimeType": "text/html",
                "body": {
                    "data": html_body.encode().hex()
                }
            }
        }

        # Act
        body = await email_service.get_message_body(message_id)

        # Assert
        assert "M12345" in body
        assert "<html>" not in body  # HTML tags removed

    @pytest.mark.asyncio
    async def test_poll_inbox_extracts_metadata(
        self, email_service, mock_gmail_service
    ):
        """
        Test email metadata extraction

        Given: Email with headers and attachments
        When: poll_inbox() is called
        Then: Complete metadata extracted (sender, subject, date, attachments)
        """
        # Arrange
        mock_gmail_service.users().messages().get().execute.return_value = {
            "id": "msg_123",
            "payload": {
                "headers": [
                    {"name": "From", "value": "john.doe@client.com"},
                    {"name": "Subject", "value": "Medical Claim Submission"},
                    {"name": "Date", "value": "Wed, 18 Dec 2024 10:42:00 +0800"},
                ],
                "parts": [
                    {
                        "filename": "receipt_001.jpg",
                        "body": {"attachmentId": "att_123", "size": 245678},
                    },
                    {
                        "filename": "receipt_002.jpg",
                        "body": {"attachmentId": "att_456", "size": 198765},
                    },
                ],
            },
        }

        # Act
        emails = await email_service.poll_inbox()

        # Assert
        assert len(emails) > 0
        email = emails[0]

        assert email.sender == "john.doe@client.com"
        assert email.subject == "Medical Claim Submission"
        assert email.received_at is not None
        assert len(email.attachments) == 2

    @pytest.mark.asyncio
    async def test_poll_inbox_handles_no_attachments(
        self, email_service, mock_gmail_service
    ):
        """
        Test handling of emails without attachments

        Given: Email query returns email without attachments
        When: poll_inbox() is called
        Then: Email is skipped
        """
        # Arrange
        mock_gmail_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg_noattach"}],
            "nextPageToken": None,
        }

        mock_gmail_service.users().messages().get().execute.return_value = {
            "id": "msg_noattach",
            "payload": {
                "headers": [],
                "parts": [],  # No attachments
            },
        }

        # Act
        emails = await email_service.poll_inbox()

        # Assert
        # Should filter out emails without attachments
        assert all(len(email.attachments) > 0 for email in emails)

    @pytest.mark.asyncio
    async def test_poll_inbox_handles_api_errors(
        self, email_service, mock_gmail_service
    ):
        """
        Test error handling for Gmail API failures

        Given: Gmail API returns error
        When: poll_inbox() is called
        Then: Appropriate exception raised
        """
        # Arrange
        from googleapiclient.errors import HttpError

        mock_gmail_service.users().messages().list().execute.side_effect = HttpError(
            resp=MagicMock(status=500), content=b"Internal Server Error"
        )

        # Act & Assert
        with pytest.raises(Exception):
            await email_service.poll_inbox()

    @pytest.mark.asyncio
    async def test_download_attachment_retries_on_failure(
        self, email_service, mock_gmail_service, tmp_path
    ):
        """
        Test retry logic for attachment download failures

        Given: Gmail API fails on first attempt
        When: download_attachment() is called
        Then: Retries and succeeds on second attempt
        """
        # Arrange
        message_id = "msg_123"
        attachment_id = "att_456"
        destination = tmp_path / "receipt.jpg"

        # Fail first, succeed second
        mock_gmail_service.users().messages().attachments().get().execute.side_effect = [
            Exception("Network error"),
            {"data": "base64encodeddata=="},
        ]

        # Act
        result_path = await email_service.download_attachment(
            message_id, attachment_id, destination
        )

        # Assert
        assert result_path.exists()
        assert mock_gmail_service.users().messages().attachments().get().execute.call_count == 2

    @pytest.mark.asyncio
    async def test_poll_inbox_respects_interval(
        self, email_service, mock_gmail_service
    ):
        """
        Test that polling respects configured interval

        Given: Poll interval set to 30 seconds
        When: Multiple polls executed
        Then: Interval maintained between polls
        """
        # This would be tested in integration tests with actual timing
        # Unit test just verifies config is read
        assert email_service.config.poll_interval_seconds == 30

    @pytest.mark.asyncio
    async def test_handles_multiple_attachments_per_email(
        self, email_service, mock_gmail_service
    ):
        """
        Test handling emails with multiple attachments

        Given: Email with 3 attached receipts
        When: Email processed
        Then: All 3 attachments identified in metadata
        """
        # Arrange
        mock_gmail_service.users().messages().get().execute.return_value = {
            "id": "msg_multi",
            "payload": {
                "headers": [
                    {"name": "From", "value": "test@example.com"},
                    {"name": "Subject", "value": "Multiple Claims"},
                ],
                "parts": [
                    {"filename": "receipt1.jpg", "body": {"attachmentId": "att_1"}},
                    {"filename": "receipt2.jpg", "body": {"attachmentId": "att_2"}},
                    {"filename": "receipt3.pdf", "body": {"attachmentId": "att_3"}},
                ],
            },
        }

        # Act
        emails = await email_service.poll_inbox()

        # Assert
        assert len(emails[0].attachments) == 3
