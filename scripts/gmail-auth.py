#!/usr/bin/env python3
"""
Gmail OAuth2 Authorization Script

Run this script ONCE to authorize Gmail access for personal Gmail accounts.
This opens a browser window for you to login and grant permissions.

Usage:
    python scripts/gmail-auth.py
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

# Gmail API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]

# Paths
CREDENTIALS_PATH = "secrets/gmail-oauth-credentials.json"
TOKEN_PATH = "secrets/gmail_token.json"


def main():
    """Run Gmail OAuth2 authorization flow."""
    print("=" * 60)
    print("Gmail OAuth2 Authorization")
    print("=" * 60)
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
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # Refresh or create new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
            print("✅ Token refreshed successfully")
        else:
            print()
            print("Starting OAuth2 authorization flow...")
            print("📋 A browser window will open for Gmail login.")
            print("   Please login and grant the requested permissions.")
            print()

            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )

            # Run local server for OAuth2 callback
            # Use port=0 to automatically find available port
            creds = flow.run_local_server(
                port=0,
                open_browser=True,
                success_message="✅ Authorization successful! You can close this window.",
            )

            print()
            print("✅ Authorization successful!")

        # Save the credentials
        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

        print(f"✅ Token saved to: {TOKEN_PATH}")

    # Test the credentials
    print()
    print("Testing Gmail API connection...")
    try:
        service = build("gmail", "v1", credentials=creds)

        # Get user profile
        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress")

        print(f"✅ Successfully connected to Gmail!")
        print(f"   Email: {email}")
        print(f"   Total messages: {profile.get('messagesTotal', 0):,}")
        print()

        # List labels
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])

        print(f"📁 Found {len(labels)} labels:")
        for label in labels[:10]:  # Show first 10
            print(f"   - {label['name']}")

        if len(labels) > 10:
            print(f"   ... and {len(labels) - 10} more")

    except Exception as e:
        print(f"❌ ERROR testing Gmail API: {e}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("✅ Gmail OAuth2 setup complete!")
    print("=" * 60)
    print()
    print("You can now run the application:")
    print("  docker-compose up -d")
    print()


if __name__ == "__main__":
    main()
