"""Gmail API integration for email monitoring."""

import asyncio
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import redis.asyncio as aioredis

from src.config.settings import settings
from src.models.email import EmailAttachment, EmailMetadata
from src.utils.logging import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/drive.file",  # For Drive archiving
    "https://www.googleapis.com/auth/pubsub",  # For Gmail Watch push notifications
]

# Batch size for Gmail API requests (reduced to prevent rate limiting)
BATCH_SIZE = 25


class EmailService:
    """Gmail API integration for email monitoring."""

    def __init__(self) -> None:
        """Initialize Gmail API client."""
        self.config = settings.gmail
        self.creds: Optional[Credentials] = None
        self._authenticate()
        self.service = build("gmail", "v1", credentials=self.creds)
        self.redis: Optional[aioredis.Redis] = None
        logger.info("Gmail service initialized")

    async def connect_redis(self) -> None:
        """Connect to Redis for message ID caching."""
        try:
            self.redis = await aioredis.from_url(
                settings.redis.url,
                decode_responses=True
            )
            logger.info("Gmail service connected to Redis for caching")
        except Exception as e:
            logger.warning("Failed to connect to Redis, caching disabled", error=str(e))
            self.redis = None

    async def disconnect_redis(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            logger.info("Gmail service disconnected from Redis")

    async def _is_message_seen(self, message_id: str) -> bool:
        """Check if message ID has been seen before."""
        if not self.redis:
            return False
        try:
            return await self.redis.sismember("gmail:seen_messages", message_id)
        except Exception as e:
            logger.warning("Failed to check seen message", message_id=message_id, error=str(e))
            return False

    async def _mark_message_seen(self, message_id: str) -> None:
        """Mark message ID as seen (TTL: 30 days)."""
        if not self.redis:
            return
        try:
            await self.redis.sadd("gmail:seen_messages", message_id)
            await self.redis.expire("gmail:seen_messages", 30 * 24 * 60 * 60)  # 30 days
        except Exception as e:
            logger.warning("Failed to mark message as seen", message_id=message_id, error=str(e))

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
                try:
                    self.creds.refresh(Request())
                    logger.info("Gmail token refreshed")

                    # Save refreshed token
                    self.config.token_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.config.token_path, "w") as token:
                        token.write(self.creds.to_json())
                except Exception as e:
                    logger.error("Failed to refresh Gmail token", error=str(e))
                    raise RuntimeError(
                        "Gmail token refresh failed. Please run "
                        "'python scripts/generate_gmail_token_pubsub.py' to reauthorize."
                    ) from e
            else:
                # Cannot run browser-based OAuth in headless environment
                raise RuntimeError(
                    "Gmail token not found or invalid. Please run "
                    "'python scripts/generate_gmail_token_pubsub.py' on a machine with a browser "
                    "to generate the token, then copy secrets/gmail_token.json to the server."
                )

    async def poll_inbox(self) -> list[EmailMetadata]:
        """
        Poll inbox for unread emails with attachments using batch requests.

        Returns:
            List of email metadata for new emails (max 25 at a time)
        """
        try:
            # Query for unread emails with attachments, not processed
            query = f"has:attachment is:unread -label:{self.config.processed_label}"

            # Fetch message IDs (only IDs, not full metadata yet)
            results = await asyncio.to_thread(
                lambda: self.service.users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    maxResults=BATCH_SIZE,  # Limit to 25 to prevent rate limiting
                    fields="messages(id),nextPageToken"  # Only IDs
                )
                .execute()
            )

            all_messages = results.get("messages", [])
            logger.info("Polled inbox", found_messages=len(all_messages))

            if not all_messages:
                return []

            # Filter out messages we've already seen
            unseen_message_ids = []
            for msg in all_messages:
                msg_id = msg["id"]
                if not await self._is_message_seen(msg_id):
                    unseen_message_ids.append(msg_id)
                else:
                    logger.debug("Skipping already seen message", message_id=msg_id)

            if not unseen_message_ids:
                logger.info("All messages already seen, skipping metadata fetch")
                return []

            logger.info(
                "Fetching metadata for unseen messages",
                unseen_count=len(unseen_message_ids),
                total_count=len(all_messages)
            )

            # Fetch metadata using batch request (single HTTP call)
            email_list = await self._fetch_metadata_batch(unseen_message_ids)

            # Mark all successfully fetched messages as seen
            for email in email_list:
                await self._mark_message_seen(email.message_id)

            return email_list

        except Exception as e:
            logger.error("Failed to poll inbox", error=str(e))
            raise

    async def _fetch_metadata_batch(self, message_ids: list[str]) -> list[EmailMetadata]:
        """
        Fetch metadata for multiple messages using a single batch request.

        Args:
            message_ids: List of message IDs to fetch

        Returns:
            List of EmailMetadata objects
        """
        email_list = []
        errors = []

        def callback(request_id, response, exception):
            """Callback for batch request."""
            if exception is not None:
                errors.append({"message_id": request_id, "error": str(exception)})
                logger.warning("Error fetching message in batch", message_id=request_id, error=str(exception))
            else:
                try:
                    # Parse response into EmailMetadata
                    headers = {h["name"]: h["value"] for h in response["payload"]["headers"]}

                    # Extract attachments from payload
                    attachments = []
                    if "parts" in response["payload"]:
                        for part in response["payload"]["parts"]:
                            if part.get("filename"):
                                attachments.append(part["filename"])

                    metadata = EmailMetadata(
                        message_id=request_id,
                        sender=headers.get("From", ""),
                        subject=headers.get("Subject", ""),
                        received_at=datetime.fromtimestamp(int(response["internalDate"]) / 1000),
                        attachments=attachments,
                        labels=response.get("labelIds", []),
                    )
                    email_list.append(metadata)
                except Exception as e:
                    errors.append({"message_id": request_id, "error": str(e)})
                    logger.error("Failed to parse message metadata", message_id=request_id, error=str(e))

        # Execute batch request in thread pool
        await asyncio.to_thread(self._execute_batch_request, message_ids, callback)

        if errors:
            logger.warning("Batch request completed with errors", error_count=len(errors))

        logger.info(
            "Batch metadata fetch completed",
            requested=len(message_ids),
            successful=len(email_list),
            failed=len(errors)
        )

        return email_list

    def _execute_batch_request(self, message_ids: list[str], callback) -> None:
        """
        Execute synchronous batch request (runs in thread pool).

        Args:
            message_ids: List of message IDs
            callback: Callback function for results
        """
        batch = self.service.new_batch_http_request(callback=callback)

        for msg_id in message_ids:
            batch.add(
                self.service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="metadata",  # Only metadata, not full message body
                    metadataHeaders=["Subject", "From", "Date"]  # Only essential headers
                ),
                request_id=msg_id
            )

        # Execute the batch (single HTTP request for all messages)
        batch.execute()

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
            # Get message with attachments (non-blocking)
            message = await asyncio.to_thread(
                lambda: self.service.users()
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

            # Download attachment (non-blocking)
            attachment = await asyncio.to_thread(
                lambda: self.service.users()
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

            # Modify message (non-blocking)
            await asyncio.to_thread(
                lambda: self.service.users().messages().modify(
                    userId="me",
                    id=message_id,
                    body={"addLabelIds": [label_id], "removeLabelIds": ["UNREAD"]},
                ).execute()
            )

            logger.info("Email marked as processed", message_id=message_id)

        except Exception as e:
            logger.error("Failed to mark email as processed", message_id=message_id, error=str(e))
            raise

    async def _get_or_create_label(self, label_name: str) -> str:
        """Get or create Gmail label."""
        try:
            # List existing labels (non-blocking)
            results = await asyncio.to_thread(
                lambda: self.service.users().labels().list(userId="me").execute()
            )
            labels = results.get("labels", [])

            # Check if label exists
            for label in labels:
                if label["name"] == label_name:
                    return label["id"]

            # Create new label (non-blocking)
            label = await asyncio.to_thread(
                lambda: self.service.users()
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
            # Get message (non-blocking)
            message = await asyncio.to_thread(
                lambda: self.service.users()
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
