"""
Pytest configuration and shared fixtures
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from _pytest.monkeypatch import MonkeyPatch

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_data_dir() -> Path:
    """Return path to test data directory."""
    return TEST_DATA_DIR


@pytest.fixture
def mock_env(monkeypatch: MonkeyPatch) -> None:
    """Set up mock environment variables for testing."""
    env_vars = {
        "APP_ENV": "testing",
        "APP_DEBUG": "true",
        "LOG_LEVEL": "DEBUG",
        "GMAIL_CREDENTIALS_PATH": "/tmp/test_gmail_creds.json",
        "GMAIL_TOKEN_PATH": "/tmp/test_gmail_token.json",
        "GMAIL_INBOX_LABEL": "INBOX",
        "GMAIL_POLL_INTERVAL": "30",
        "NCB_API_BASE_URL": "http://test.ncb.api",
        "NCB_API_KEY": "test-api-key-12345",
        "NCB_TIMEOUT": "30",
        "SHEETS_CREDENTIALS_PATH": "/tmp/test_sheets_creds.json",
        "SHEETS_SPREADSHEET_ID": "test-spreadsheet-id",
        "DRIVE_CREDENTIALS_PATH": "/tmp/test_drive_creds.json",
        "DRIVE_FOLDER_ID": "test-folder-id",
        "REDIS_URL": "redis://localhost:6379/1",
        "OCR_USE_GPU": "false",
        "OCR_DEFAULT_LANGUAGE": "en",
        "OCR_CONFIDENCE_THRESHOLD": "0.75",
        "ADMIN_API_KEY": "test-admin-key",
        "ADMIN_PORT": "8080",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def sample_receipt_data() -> dict:
    """Return sample extracted claim data."""
    return {
        "member_id": "M12345",
        "member_name": "John Doe",
        "provider_name": "City Medical Centre",
        "provider_address": "123 Main St, Kuala Lumpur",
        "service_date": "2024-12-15",
        "receipt_number": "RCP-2024-001234",
        "total_amount": 150.00,
        "currency": "MYR",
        "itemized_charges": [
            {"description": "Consultation", "amount": 80.00},
            {"description": "Medication", "amount": 70.00}
        ],
        "gst_amount": None,
        "sst_amount": 9.00,
    }


@pytest.fixture
def sample_email_metadata() -> dict:
    """Return sample email metadata."""
    return {
        "message_id": "msg_abc123xyz",
        "sender": "john.doe@client.com",
        "subject": "Medical Claim - December 2024",
        "received_at": datetime(2024, 12, 18, 10, 42, 0),
        "attachments": ["receipt_001.jpg"],
        "labels": ["INBOX", "UNREAD"],
    }


@pytest.fixture
def sample_job_data() -> dict:
    """Return sample job data."""
    return {
        "id": "job_test123",
        "email_id": "msg_abc123xyz",
        "attachment_filename": "receipt_001.jpg",
        "attachment_path": "/tmp/attachments/receipt_001.jpg",
        "attachment_hash": "sha256:abc123def456",
        "status": "pending",
        "created_at": datetime(2024, 12, 18, 10, 42, 0),
        "updated_at": datetime(2024, 12, 18, 10, 42, 0),
    }


@pytest.fixture
async def mock_redis() -> AsyncMock:
    """Return mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.ping.return_value = True
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.exists.return_value = 0
    return redis_mock


@pytest.fixture
def mock_gmail_service() -> MagicMock:
    """Return mock Gmail service."""
    service_mock = MagicMock()
    service_mock.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg_123"}],
        "nextPageToken": None,
    }
    service_mock.users().messages().get().execute.return_value = {
        "id": "msg_123",
        "payload": {
            "headers": [
                {"name": "From", "value": "test@example.com"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "Wed, 18 Dec 2024 10:42:00 +0800"},
            ],
            "parts": [
                {
                    "filename": "receipt.jpg",
                    "body": {"attachmentId": "att_123"},
                }
            ],
        },
    }
    return service_mock


@pytest.fixture
def mock_ncb_api() -> AsyncMock:
    """Return mock NCB API client."""
    api_mock = AsyncMock()
    api_mock.post.return_value = MagicMock(
        status_code=201,
        json=lambda: {
            "success": True,
            "claim_reference": "CLM-2024-567890",
            "status": "received",
            "message": "Claim submitted successfully",
        },
    )
    return api_mock


@pytest.fixture
def mock_sheets_service() -> MagicMock:
    """Return mock Google Sheets service."""
    service_mock = MagicMock()
    service_mock.spreadsheets().values().append().execute.return_value = {
        "updates": {
            "updatedRange": "Sheet1!A142:L142",
            "updatedRows": 1,
        }
    }
    return service_mock


@pytest.fixture
def mock_drive_service() -> MagicMock:
    """Return mock Google Drive service."""
    service_mock = MagicMock()
    service_mock.files().create().execute.return_value = {
        "id": "file_abc123",
        "name": "receipt_001.jpg",
        "webViewLink": "https://drive.google.com/file/d/file_abc123/view",
    }
    return service_mock


@pytest.fixture
def mock_ocr_engine() -> MagicMock:
    """Return mock OCR engine."""
    ocr_mock = MagicMock()
    # Mock OCR result format from PaddleOCR
    ocr_mock.ocr.return_value = [
        [
            # Each element: [[box_coordinates], (text, confidence)]
            [[[10, 10], [100, 10], [100, 30], [10, 30]], ("City Medical Centre", 0.98)],
            [[[10, 40], [100, 40], [100, 60], [10, 60]], ("Receipt No: RCP-2024-001234", 0.95)],
            [[[10, 70], [100, 70], [100, 90], [10, 90]], ("Date: 15/12/2024", 0.92)],
            [[[10, 100], [100, 100], [100, 120], [10, 120]], ("Total: RM 150.00", 0.94)],
            [[[10, 130], [100, 130], [100, 150], [10, 150]], ("SST (6%): RM 9.00", 0.91)],
        ]
    ]
    return ocr_mock


@pytest.fixture
def malaysian_receipt_samples() -> dict:
    """Return sample Malaysian receipt text patterns."""
    return {
        "english": {
            "text": """
            City Medical Centre
            123 Main Street, Kuala Lumpur
            Tel: 03-12345678

            Receipt No: RCP-2024-001234
            Date: 15/12/2024
            Time: 14:30

            Patient Name: John Doe
            Member ID: M12345

            Description              Amount (RM)
            ------------------------------------
            Consultation                  80.00
            Medication                    70.00
            ------------------------------------
            Subtotal                     150.00
            SST (6%)                       9.00
            ------------------------------------
            Total                        159.00

            Thank you for your visit!
            """,
            "expected": {
                "provider_name": "City Medical Centre",
                "receipt_number": "RCP-2024-001234",
                "service_date": "15/12/2024",
                "member_id": "M12345",
                "member_name": "John Doe",
                "total_amount": 159.00,
                "sst_amount": 9.00,
            }
        },
        "malay": {
            "text": """
            Klinik Kesihatan Jaya
            No. 45, Jalan Utama, Petaling Jaya

            Resit No: INV-2024-5678
            Tarikh: 15-12-2024

            Nama Pesakit: Ahmad bin Ali
            No. Ahli: M67890

            Perkhidmatan            Harga (RM)
            ------------------------------------
            Rawatan                       60.00
            Ubat                          40.00
            ------------------------------------
            Jumlah                       100.00
            SST (6%)                       6.00
            ------------------------------------
            Jumlah Keseluruhan           106.00

            Terima kasih!
            """,
            "expected": {
                "provider_name": "Klinik Kesihatan Jaya",
                "receipt_number": "INV-2024-5678",
                "service_date": "15-12-2024",
                "member_id": "M67890",
                "member_name": "Ahmad bin Ali",
                "total_amount": 106.00,
                "sst_amount": 6.00,
            }
        },
    }


@pytest.fixture
def confidence_test_cases() -> list[dict]:
    """Return test cases for confidence threshold routing."""
    return [
        {
            "name": "high_confidence_auto_submit",
            "confidence": 0.95,
            "expected_level": "high",
            "expected_action": "auto_submit",
        },
        {
            "name": "medium_confidence_review",
            "confidence": 0.82,
            "expected_level": "medium",
            "expected_action": "submit_with_review",
        },
        {
            "name": "low_confidence_exception",
            "confidence": 0.68,
            "expected_level": "low",
            "expected_action": "exception_queue",
        },
        {
            "name": "boundary_high",
            "confidence": 0.90,
            "expected_level": "high",
            "expected_action": "auto_submit",
        },
        {
            "name": "boundary_medium",
            "confidence": 0.75,
            "expected_level": "medium",
            "expected_action": "submit_with_review",
        },
        {
            "name": "boundary_low",
            "confidence": 0.74,
            "expected_level": "low",
            "expected_action": "exception_queue",
        },
    ]
