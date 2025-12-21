"""Google Drive service for attachment archiving."""

import datetime
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.config.settings import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class DriveService:
    """Google Drive archive service."""

    def __init__(self) -> None:
        """Initialize Drive API client."""
        self.config = settings.drive
        credentials = Credentials.from_service_account_file(
            str(self.config.credentials_path), scopes=SCOPES
        )
        self.service = build("drive", "v3", credentials=credentials)
        logger.info("Drive service initialized", folder_id=self.config.folder_id)

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
            # Create date-based folder structure
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

            file = (
                self.service.files()
                .create(body=file_metadata, media_body=media, fields="id,webViewLink")
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
            file = self.service.files().get(fileId=file_id, fields="webViewLink").execute()
            return file.get("webViewLink", "")

        except Exception as e:
            logger.error("Failed to get file URL", file_id=file_id, error=str(e))
            return ""

    async def _get_or_create_folder(self, folder_name: str, parent_id: str) -> str:
        """Get or create folder in Drive."""
        try:
            # Search for existing folder
            query = (
                f"name='{folder_name}' and "
                f"'{parent_id}' in parents and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"trashed=false"
            )

            results = (
                self.service.files()
                .list(q=query, spaces="drive", fields="files(id, name)")
                .execute()
            )

            folders = results.get("files", [])

            if folders:
                return folders[0]["id"]

            # Create new folder
            folder_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }

            folder = (
                self.service.files()
                .create(body=folder_metadata, fields="id")
                .execute()
            )

            logger.debug("Created Drive folder", folder_name=folder_name, folder_id=folder["id"])
            return folder["id"]

        except Exception as e:
            logger.error("Failed to get/create folder", folder_name=folder_name, error=str(e))
            raise
