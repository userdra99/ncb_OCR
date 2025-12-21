"""Gmail API integration for email monitoring."""

import base64
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.config.settings import settings
from src.models.email import EmailAttachment, EmailMetadata
from src.utils.logging import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]


class EmailService:
    """Gmail API integration for email monitoring."""

    def __init__(self) -> None:
        """Initialize Gmail API client."""
        self.config = settings.gmail
        self.creds: Optional[Credentials] = None
        self._authenticate()
        self.service = build("gmail", "v1", credentials=self.creds)
        logger.info("Gmail service initialized")

    def _authenticate(self) -> None:
        """Authenticate with Gmail API using OAuth."""
        # Load existing token
        if self.config.token_path.exists():
            self.creds = Credentials.from_authorized_user_file(
                str(self.config.token_path), SCOPES
            )

        # Refresh or get new token
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
                logger.info("Gmail token refreshed")
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.config.credentials_path), SCOPES
                )
                self.creds = flow.run_local_server(port=0)
                logger.info("New Gmail token obtained")

            # Save token
            self.config.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config.token_path, "w") as token:
                token.write(self.creds.to_json())

    async def poll_inbox(self) -> list[EmailMetadata]:
        """
        Poll inbox for unread emails with attachments.

        Returns:
            List of email metadata for new emails
        """
        try:
            # Query for unread emails with attachments, not processed
            query = f"has:attachment is:unread -label:{self.config.processed_label}"

            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=50)
                .execute()
            )

            messages = results.get("messages", [])
            logger.info("Polled inbox", found_messages=len(messages))

            email_list = []
            for msg in messages:
                metadata = await self._get_message_metadata(msg["id"])
                if metadata:
                    email_list.append(metadata)

            return email_list

        except Exception as e:
            logger.error("Failed to poll inbox", error=str(e))
            raise

    async def _get_message_metadata(self, message_id: str) -> Optional[EmailMetadata]:
        """Get message metadata."""
        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}

            # Extract attachments
            attachments = []
            if "parts" in message["payload"]:
                for part in message["payload"]["parts"]:
                    if part.get("filename"):
                        attachments.append(part["filename"])

            return EmailMetadata(
                message_id=message_id,
                sender=headers.get("From", ""),
                subject=headers.get("Subject", ""),
                received_at=datetime.fromtimestamp(int(message["internalDate"]) / 1000),
                attachments=attachments,
                labels=message.get("labelIds", []),
            )

        except Exception as e:
            logger.error("Failed to get message metadata", message_id=message_id, error=str(e))
            return None

    async def download_attachment(
        self, message_id: str, filename: str, destination: Path
    ) -> Path:
        """
        Download attachment to local storage.

        Args:
            message_id: Gmail message ID
            filename: Attachment filename to download
            destination: Local path for download

        Returns:
            Path to downloaded file
        """
        try:
            # Get message with attachments
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            # Find attachment
            attachment_id = None
            if "parts" in message["payload"]:
                for part in message["payload"]["parts"]:
                    if part.get("filename") == filename:
                        attachment_id = part["body"].get("attachmentId")
                        break

            if not attachment_id:
                raise ValueError(f"Attachment {filename} not found in message {message_id}")

            # Download attachment
            attachment = (
                self.service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )

            # Decode and save
            file_data = base64.urlsafe_b64decode(attachment["data"])
            destination.parent.mkdir(parents=True, exist_ok=True)

            with open(destination, "wb") as f:
                f.write(file_data)

            logger.info(
                "Attachment downloaded",
                message_id=message_id,
                filename=filename,
                size_bytes=len(file_data),
            )

            return destination

        except Exception as e:
            logger.error(
                "Failed to download attachment",
                message_id=message_id,
                filename=filename,
                error=str(e),
            )
            raise

    async def mark_as_processed(self, message_id: str) -> None:
        """Mark email as read and apply processed label."""
        try:
            # Get or create processed label
            label_id = await self._get_or_create_label(self.config.processed_label)

            # Modify message
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": [label_id], "removeLabelIds": ["UNREAD"]},
            ).execute()

            logger.info("Email marked as processed", message_id=message_id)

        except Exception as e:
            logger.error("Failed to mark email as processed", message_id=message_id, error=str(e))
            raise

    async def _get_or_create_label(self, label_name: str) -> str:
        """Get or create Gmail label."""
        try:
            # List existing labels
            results = self.service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])

            # Check if label exists
            for label in labels:
                if label["name"] == label_name:
                    return label["id"]

            # Create new label
            label = (
                self.service.users()
                .labels()
                .create(
                    userId="me",
                    body={
                        "name": label_name,
                        "labelListVisibility": "labelShow",
                        "messageListVisibility": "show",
                    },
                )
                .execute()
            )

            logger.info("Created new label", label_name=label_name)
            return label["id"]

        except Exception as e:
            logger.error("Failed to get/create label", label_name=label_name, error=str(e))
            raise

    async def get_message_body(self, message_id: str) -> str:
        """Extract plain text body from email."""
        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            # Extract body text
            def _get_body(payload):
                if "body" in payload and "data" in payload["body"]:
                    return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
                if "parts" in payload:
                    for part in payload["parts"]:
                        if part["mimeType"] == "text/plain":
                            if "data" in part["body"]:
                                return base64.urlsafe_b64decode(part["body"]["data"]).decode(
                                    "utf-8"
                                )
                return ""

            return _get_body(message["payload"])

        except Exception as e:
            logger.error("Failed to get message body", message_id=message_id, error=str(e))
            return ""
