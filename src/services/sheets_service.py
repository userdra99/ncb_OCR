"""Google Sheets service for audit logging."""

import asyncio
import datetime
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from src.config.settings import settings
from src.models.extraction import ExtractionResult
from src.models.job import Job
from src.utils.logging import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsService:
    """Google Sheets backup logging."""

    def __init__(self) -> None:
        """Initialize Sheets API client."""
        self.config = settings.sheets
        credentials = Credentials.from_service_account_file(
            str(self.config.credentials_path), scopes=SCOPES
        )
        self.client = gspread.authorize(credentials)
        self.spreadsheet = self.client.open_by_key(self.config.spreadsheet_id)
        logger.info("Sheets service initialized", spreadsheet_id=self.config.spreadsheet_id)

    async def log_extraction(self, job: Job, extraction: ExtractionResult) -> str:
        """
        Log extraction to Google Sheets.

        Args:
            job: Processing job
            extraction: Extraction result

        Returns:
            Sheet row reference (e.g., "Sheet1!A142")
        """
        try:
            # Get current sheet (or create monthly sheet)
            sheet = await asyncio.to_thread(self._get_or_create_current_sheet)

            # Prepare row data
            row = [
                datetime.datetime.now().isoformat(),  # Timestamp
                job.email_id,  # Email ID
                "",  # Sender (to be filled from email metadata)
                job.attachment_filename,  # Attachment filename
                extraction.claim.member_id or "",  # Member ID
                extraction.claim.provider_name or "",  # Provider name
                extraction.claim.total_amount or 0.0,  # Amount
                extraction.confidence_score,  # Confidence score
                job.status.value,  # Status
                job.ncb_reference or "",  # NCB reference
                job.ncb_submitted_at.isoformat() if job.ncb_submitted_at else "",  # NCB submit time
                job.error_message or "",  # Error message
                "YES" if job.needs_review else "NO",  # Needs review flag
                job.exception_reason or "",  # Exception reason
            ]

            # Append row (non-blocking)
            await asyncio.to_thread(
                lambda: sheet.append_row(row, value_input_option="USER_ENTERED")
            )

            # Get row number (non-blocking)
            all_values = await asyncio.to_thread(sheet.get_all_values)
            row_num = len(all_values)
            row_ref = f"{sheet.title}!A{row_num}"

            logger.info("Extraction logged to Sheets", job_id=job.id, row_ref=row_ref)
            return row_ref

        except Exception as e:
            logger.error("Failed to log extraction to Sheets", job_id=job.id, error=str(e))
            raise

    async def update_ncb_status(
        self, row_ref: str, ncb_reference: str, status: str
    ) -> None:
        """
        Update row with NCB submission status.

        Args:
            row_ref: Sheet row reference (e.g., "Sheet1!A142")
            ncb_reference: NCB claim reference
            status: Status string
        """
        try:
            # Parse row reference
            sheet_name, cell = row_ref.split("!")
            row_num = int(cell[1:])

            # Get worksheet (non-blocking)
            sheet = await asyncio.to_thread(
                lambda: self.spreadsheet.worksheet(sheet_name)
            )

            # Update columns J (NCB reference) and I (status) in parallel
            timestamp = datetime.datetime.now().isoformat()
            await asyncio.gather(
                asyncio.to_thread(lambda: sheet.update(f"I{row_num}", [[status]])),
                asyncio.to_thread(lambda: sheet.update(f"J{row_num}", [[ncb_reference]])),
                asyncio.to_thread(lambda: sheet.update(f"K{row_num}", [[timestamp]])),
            )

            logger.info(
                "NCB status updated in Sheets",
                row_ref=row_ref,
                ncb_reference=ncb_reference,
            )

        except Exception as e:
            logger.error("Failed to update NCB status", row_ref=row_ref, error=str(e))
            raise

    async def get_daily_summary(self, date: datetime.date) -> dict:
        """
        Get processing summary for date.

        Args:
            date: Date to summarize

        Returns:
            Summary statistics
        """
        try:
            # Get sheet and values (non-blocking)
            sheet = await asyncio.to_thread(self._get_or_create_current_sheet)
            all_values = await asyncio.to_thread(sheet.get_all_values)

            # Filter by date
            date_str = date.isoformat()
            matching_rows = [
                row for row in all_values[1:] if row[0].startswith(date_str)  # Skip header
            ]

            total = len(matching_rows)
            successful = sum(1 for row in matching_rows if row[8] == "submitted")
            exceptions = sum(1 for row in matching_rows if row[8] == "exception")
            failed = sum(1 for row in matching_rows if row[8] == "failed")

            return {
                "date": date_str,
                "total_processed": total,
                "successful": successful,
                "exceptions": exceptions,
                "failed": failed,
                "success_rate": successful / total if total > 0 else 0.0,
            }

        except Exception as e:
            logger.error("Failed to get daily summary", date=date, error=str(e))
            return {}

    def _get_or_create_current_sheet(self):
        """
        Get or create sheet for current month.

        Note: This method is synchronous and should be called via asyncio.to_thread()
        from async contexts to avoid blocking the event loop.
        """
        # Monthly sheet naming: "Claims_2024_12"
        sheet_name = f"Claims_{datetime.datetime.now().strftime('%Y_%m')}"

        try:
            sheet = self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            # Create new sheet
            sheet = self.spreadsheet.add_worksheet(
                title=sheet_name, rows=1000, cols=14
            )

            # Add header row
            header = [
                "Timestamp",
                "Email ID",
                "Sender",
                "Filename",
                "Member ID",
                "Provider",
                "Amount",
                "Confidence",
                "Status",
                "NCB Reference",
                "NCB Submitted",
                "Error",
                "Needs Review",
                "Exception Reason",
            ]
            sheet.append_row(header)

            logger.info("Created new monthly sheet", sheet_name=sheet_name)

        return sheet
