"""Google Drive service for attachment archiving."""

import asyncio
import datetime
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.config.settings import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Using OAuth instead of service account for personal Google accounts
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class DriveService:
    """Google Drive archive service with OAuth authentication."""

    def __init__(self) -> None:
        """Initialize Drive API client with OAuth."""
        self.config = settings.drive
        self.creds: Optional[Credentials] = None
        self._authenticate()
        self.service = build("drive", "v3", credentials=self.creds)
        logger.info("Drive service initialized (OAuth)", folder_id=self.config.folder_id)

    def _authenticate(self) -> None:
        """Authenticate with Drive API using OAuth (shared with Gmail)."""
        # Use Gmail OAuth token (same user, add Drive scope)
        gmail_token_path = settings.gmail.token_path
        gmail_creds_path = settings.gmail.credentials_path

        # Load existing token
        if gmail_token_path.exists():
            self.creds = Credentials.from_authorized_user_file(
                str(gmail_token_path), SCOPES
            )

        # Refresh or get new token
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
                logger.info("Drive OAuth token refreshed")
            else:
                # Need to re-authorize with Drive scope
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(gmail_creds_path), SCOPES
                )
                self.creds = flow.run_local_server(port=0)
                logger.info("Drive OAuth authorization complete")

            # Save the token for future use
            gmail_token_path.write_text(self.creds.to_json())
            logger.info("Drive OAuth token saved")

    async def archive_attachment(
        self, local_path: Path, email_id: str, original_filename: str
    ) -> str:
        """
        Archive attachment to Google Drive.

        Args:
            local_path: Path to local file
            email_id: Source email ID
            original_filename: Original attachment name

        Returns:
            Google Drive file ID

        Folder structure: /claims/{YYYY}/{MM}/{DD}/{email_id}_{filename}
        """
        try:
            # Create date-based folder structure (all folders created in parallel)
            now = datetime.datetime.now()
            year_folder = await self._get_or_create_folder(
                str(now.year), self.config.folder_id
            )
            month_folder = await self._get_or_create_folder(
                f"{now.month:02d}", year_folder
            )
            day_folder = await self._get_or_create_folder(f"{now.day:02d}", month_folder)

            # Upload file
            filename = f"{email_id}_{original_filename}"
            file_metadata = {
                "name": filename,
                "parents": [day_folder],
                "properties": {
                    "email_id": email_id,
                    "processed_at": now.isoformat(),
                    "original_filename": original_filename,
                },
            }

            media = MediaFileUpload(str(local_path), resumable=True)

            # Upload file (non-blocking)
            # Note: supportsAllDrives not needed for personal Drive with OAuth
            file = await asyncio.to_thread(
                lambda: self.service.files()
                .create(
                    body=file_metadata,
                    media_body=media,
                    fields="id,webViewLink",
                )
                .execute()
            )

            logger.info(
                "Attachment archived to Drive",
                email_id=email_id,
                filename=filename,
                file_id=file["id"],
            )

            return file["id"]

        except Exception as e:
            logger.error(
                "Failed to archive attachment",
                email_id=email_id,
                filename=original_filename,
                error=str(e),
            )
            raise

    async def get_file_url(self, file_id: str) -> str:
        """Get shareable URL for archived file."""
        try:
            # Get file info (non-blocking)
            file = await asyncio.to_thread(
                lambda: self.service.files()
                .get(fileId=file_id, fields="webViewLink")
                .execute()
            )
            return file.get("webViewLink", "")

        except Exception as e:
            logger.error("Failed to get file URL", file_id=file_id, error=str(e))
            return ""

    async def _get_or_create_folder(self, folder_name: str, parent_id: str) -> str:
        """Get or create folder in Drive."""
        try:
            # Search for existing folder (non-blocking)
            query = (
                f"name='{folder_name}' and "
                f"'{parent_id}' in parents and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"trashed=false"
            )

            results = await asyncio.to_thread(
                lambda: self.service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name)",
                )
                .execute()
            )

            folders = results.get("files", [])

            if folders:
                return folders[0]["id"]

            # Create new folder (non-blocking)
            folder_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }

            folder = await asyncio.to_thread(
                lambda: self.service.files()
                .create(body=folder_metadata, fields="id")
                .execute()
            )

            logger.debug("Created Drive folder", folder_name=folder_name, folder_id=folder["id"])
            return folder["id"]

        except Exception as e:
            logger.error("Failed to get/create folder", folder_name=folder_name, error=str(e))
            raise
