#!/usr/bin/env python3
"""
Gmail + Drive OAuth2 Authorization Script

Run this script to authorize Gmail and Google Drive access.
Opens a browser window for you to login and grant permissions.

Usage:
    python scripts/gmail-drive-auth.py
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Combined Gmail + Drive scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/drive.file",  # ✅ Added Drive scope
]

# Paths
CREDENTIALS_PATH = "secrets/gmail-oauth-credentials.json"
TOKEN_PATH = "secrets/gmail_token.json"


def main():
    """Run OAuth2 authorization flow for Gmail + Drive."""
    print("=" * 70)
    print("Gmail + Google Drive OAuth2 Authorization")
    print("=" * 70)
    print()

    # Check if credentials file exists
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"❌ ERROR: OAuth2 credentials file not found!")
        print(f"   Expected: {CREDENTIALS_PATH}")
        print()
        print("Please follow these steps:")
        print("1. Go to: https://console.cloud.google.com/apis/credentials")
        print("2. Click 'Create Credentials' → 'OAuth client ID'")
        print("3. Application type: 'Desktop app'")
        print("4. Download JSON and save as:", CREDENTIALS_PATH)
        print()
        sys.exit(1)

    creds = None

    # Check if token already exists
    if os.path.exists(TOKEN_PATH):
        print(f"Found existing token: {TOKEN_PATH}")
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
            print("  → Loading credentials from token file...")
        except Exception as e:
            print(f"  → Failed to load token: {e}")
            creds = None

    # Validate or refresh credentials
    if creds and creds.valid:
        print("  ✅ Credentials are valid!")

    elif creds and creds.expired and creds.refresh_token:
        print("  ⚠️  Token expired, refreshing...")
        try:
            creds.refresh(Request())
            print("  ✅ Token refreshed successfully!")
        except Exception as e:
            print(f"  ❌ Failed to refresh token: {e}")
            print("  → Will re-authorize...")
            creds = None

    else:
        print("  → No valid credentials found, starting OAuth flow...")

    # Run OAuth flow if needed
    if not creds:
        print()
        print("🌐 Starting OAuth authorization flow...")
        print("   Please login and grant permissions for:")
        print("   • Gmail (read, modify, labels)")
        print("   • Google Drive (file access)")
        print()

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )

            # Try to run local server (will open browser automatically)
            # If it fails (e.g., no browser), it will show a URL to visit
            print("   Attempting to open browser...")
            try:
                creds = flow.run_local_server(port=0)
                print("  ✅ Authorization successful!")
            except:
                # Fallback: manual authorization
                print("\n   ⚠️  Could not open browser automatically.")
                print("   Please visit this URL manually:\n")
                auth_url, _ = flow.authorization_url(prompt='consent')
                print(f"   {auth_url}\n")
                code = input("   Enter authorization code: ").strip()
                flow.fetch_token(code=code)
                creds = flow.credentials
                print("  ✅ Authorization successful!")

        except Exception as e:
            print(f"  ❌ Authorization failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    # Save credentials
    print()
    print(f"💾 Saving credentials to: {TOKEN_PATH}")
    with open(TOKEN_PATH, 'w') as token:
        token.write(creds.to_json())
    print("  ✅ Credentials saved!")

    # Test access
    print()
    print("🔍 Testing API access...")
    print()

    # Test Gmail API
    try:
        gmail = build('gmail', 'v1', credentials=creds)
        profile = gmail.users().getProfile(userId='me').execute()
        print(f"  ✅ Gmail API: {profile.get('emailAddress')}")
    except Exception as e:
        print(f"  ❌ Gmail API failed: {e}")

    # Test Drive API
    try:
        drive = build('drive', 'v3', credentials=creds)
        about = drive.about().get(fields='user').execute()
        print(f"  ✅ Drive API: {about.get('user', {}).get('emailAddress', 'connected')}")
    except Exception as e:
        print(f"  ❌ Drive API failed: {e}")

    print()
    print("=" * 70)
    print("✅ Authorization complete!")
    print("=" * 70)
    print()
    print("You can now:")
    print("  • Use Gmail API to read/modify emails")
    print("  • Upload files to Google Drive")
    print()


if __name__ == '__main__':
    main()
