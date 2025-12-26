#!/usr/bin/env python3
"""
Generate JSON files from OCR extractions and upload to Google Shared Drive.
Bypasses NCB API - just generates JSON files for manual review/processing.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.config.settings import settings
from src.models.extraction import ExtractedClaim
from src.services.queue_service import QueueService
from src.services.sheets_service import SheetsService
from src.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


class JSONGeneratorUploader:
    """Generate JSON files from extractions and upload to Shared Drive."""

    def __init__(self):
        """Initialize services."""
        self.queue_service = QueueService()
        self.sheets_service = SheetsService()
        self.output_dir = Path("/app/data/json_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_drive_service(self):
        """Get Google Drive service with Shared Drive support."""
        creds = Credentials.from_service_account_file(
            settings.drive_credentials_path,
            scopes=['https://www.googleapis.com/auth/drive']
        )
        return build('drive', 'v3', credentials=creds)

    def extract_to_ncb_format(self, extraction: ExtractedClaim, job_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert extraction to NCB JSON format.

        Args:
            extraction: ExtractedClaim object
            job_metadata: Job metadata (email_id, filename, etc.)

        Returns:
            Dict in NCB API format
        """
        # Use policy_number if available, otherwise fall back to member_id
        policy_number = extraction.policy_number or extraction.member_id or "UNKNOWN"

        ncb_data = {
            "Event date": extraction.service_date.isoformat() if extraction.service_date else datetime.now(timezone.utc).date().isoformat(),
            "Submission Date": datetime.now(timezone.utc).isoformat(),
            "Claim Amount": float(extraction.total_amount),
            "Invoice Number": extraction.receipt_number or "UNKNOWN",
            "Policy Number": policy_number,
            # Include metadata for tracking
            "source_email_id": job_metadata.get("email_id", ""),
            "source_filename": job_metadata.get("filename", ""),
            "extraction_confidence": extraction.confidence_score,
            "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
            # Optional fields
            "provider_name": extraction.provider_name,
            "member_name": extraction.member_name,
            "itemized_charges": extraction.itemized_charges or [],
        }

        return ncb_data

    async def generate_json_file(self, extraction: ExtractedClaim, job_metadata: Dict[str, Any]) -> Path:
        """
        Generate JSON file for a single extraction.

        Args:
            extraction: ExtractedClaim object
            job_metadata: Job metadata

        Returns:
            Path to generated JSON file
        """
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_id = job_metadata.get("job_id", "unknown")
        filename = f"claim_{job_id}_{timestamp}.json"
        filepath = self.output_dir / filename

        # Convert to NCB format
        ncb_data = self.extract_to_ncb_format(extraction, job_metadata)

        # Write JSON file
        with open(filepath, 'w') as f:
            json.dump(ncb_data, f, indent=2, ensure_ascii=False)

        logger.info("Generated JSON file", filepath=str(filepath), job_id=job_id)
        return filepath

    async def upload_to_shared_drive(self, filepath: Path) -> str:
        """
        Upload JSON file to Google Shared Drive.

        Args:
            filepath: Path to JSON file

        Returns:
            File ID in Drive
        """
        try:
            service = self.get_drive_service()

            file_metadata = {
                'name': filepath.name,
                'parents': [settings.drive_folder_id],
                'mimeType': 'application/json'
            }

            media = MediaFileUpload(
                str(filepath),
                mimetype='application/json',
                resumable=True
            )

            # Upload with supportsAllDrives=True for Shared Drive support
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,webViewLink',
                supportsAllDrives=True  # Critical for Shared Drive
            ).execute()

            logger.info(
                "Uploaded to Shared Drive",
                filename=filepath.name,
                file_id=file['id'],
                link=file.get('webViewLink', '')
            )

            return file['id']

        except Exception as e:
            logger.error("Failed to upload to Drive", filepath=str(filepath), error=str(e))
            raise

    async def log_to_sheets(self, extraction: ExtractedClaim, job_metadata: Dict[str, Any], drive_file_id: str):
        """
        Log extraction to Google Sheets.

        Args:
            extraction: ExtractedClaim object
            job_metadata: Job metadata
            drive_file_id: Google Drive file ID
        """
        try:
            await self.sheets_service.log_extraction(
                job_id=job_metadata.get("job_id", "unknown"),
                extraction=extraction,
                email_id=job_metadata.get("email_id", ""),
                filename=job_metadata.get("filename", ""),
                status="json_generated",
                drive_file_id=drive_file_id
            )
            logger.info("Logged to Sheets", job_id=job_metadata.get("job_id"))
        except Exception as e:
            logger.error("Failed to log to Sheets", error=str(e))
            # Don't raise - logging failure shouldn't stop the process

    async def process_single_extraction(self, extraction_data: Dict[str, Any]):
        """
        Process a single extraction: generate JSON and upload.

        Args:
            extraction_data: Dict containing extraction and metadata
        """
        try:
            # Parse extraction
            extraction = ExtractedClaim(**extraction_data['extraction'])
            job_metadata = extraction_data.get('metadata', {})

            # Generate JSON file
            filepath = await self.generate_json_file(extraction, job_metadata)

            # Upload to Shared Drive
            drive_file_id = await self.upload_to_shared_drive(filepath)

            # Log to Sheets
            await self.log_to_sheets(extraction, job_metadata, drive_file_id)

            logger.info(
                "Processing complete",
                job_id=job_metadata.get("job_id"),
                drive_file_id=drive_file_id
            )

        except Exception as e:
            logger.error("Failed to process extraction", error=str(e))
            raise

    async def process_queue(self, limit: int = 10):
        """
        Process pending jobs from queue.

        Args:
            limit: Maximum number of jobs to process
        """
        logger.info("Starting queue processing", limit=limit)

        processed = 0
        for _ in range(limit):
            # Get next job from queue (if queue service supports this)
            # For now, this is a placeholder - you'd implement queue polling here
            pass

        logger.info("Queue processing complete", processed=processed)

    async def process_test_data(self):
        """Generate JSON files from test data in tests/fixtures/."""
        test_fixtures_dir = Path("/app/tests/fixtures")
        test_data_file = test_fixtures_dir / "ncb_test_data.json"

        if not test_data_file.exists():
            logger.error("Test data file not found", path=str(test_data_file))
            return

        # Load test data
        with open(test_data_file, 'r') as f:
            test_data = json.load(f)

        logger.info("Processing test data", test_cases=len(test_data.get('test_cases', [])))

        for idx, test_case in enumerate(test_data.get('test_cases', []), 1):
            try:
                # Test case is already in NCB format, save directly
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"test_claim_{idx:02d}_{timestamp}.json"
                filepath = self.output_dir / filename

                # Write JSON file
                with open(filepath, 'w') as f:
                    json.dump(test_case['input'], f, indent=2, ensure_ascii=False)

                logger.info("Generated test JSON", filename=filename)

                # Upload to Shared Drive
                drive_file_id = await self.upload_to_shared_drive(filepath)

                logger.info("Uploaded test data", filename=filename, drive_file_id=drive_file_id)

            except Exception as e:
                logger.error("Failed to process test case", index=idx, error=str(e))


async def main():
    """Main entry point."""
    logger.info("JSON Generator and Uploader starting...")

    generator = JSONGeneratorUploader()

    # For now, process test data
    # Later you can modify this to process from queue
    await generator.process_test_data()

    logger.info("JSON generation and upload complete!")


if __name__ == "__main__":
    asyncio.run(main())
