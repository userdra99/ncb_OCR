"""Pytest configuration and fixtures for all tests."""

import os
import pytest

# Set test environment variables before importing settings
os.environ["APP_ENV"] = "testing"
os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "test-project"
os.environ["GMAIL_CREDENTIALS_PATH"] = "/tmp/test_gmail_creds.json"
os.environ["GMAIL_TOKEN_PATH"] = "/tmp/test_gmail_token.json"
os.environ["NCB_API_BASE_URL"] = "https://test.ncb.example.com"
os.environ["NCB_API_KEY"] = "test-api-key"
os.environ["SHEETS_CREDENTIALS_PATH"] = "/tmp/test_sheets_creds.json"
os.environ["SHEETS_SPREADSHEET_ID"] = "test-spreadsheet-id"
os.environ["DRIVE_CREDENTIALS_PATH"] = "/tmp/test_drive_creds.json"
os.environ["DRIVE_FOLDER_ID"] = "test-folder-id"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["ADMIN_API_KEY"] = "test-admin-key"
