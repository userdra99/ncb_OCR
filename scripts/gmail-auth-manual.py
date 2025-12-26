#!/usr/bin/env python3
"""
Gmail OAuth2 Manual Authorization Script

This script generates an authorization URL that you paste in your browser manually.
Use this if the automatic browser flow doesn't work.

Usage:
    python scripts/gmail-auth-manual.py
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
]

# Paths
CREDENTIALS_PATH = "secrets/gmail-oauth-credentials.json"
TOKEN_PATH = "secrets/gmail_token.json"


def main():
    """Run Gmail OAuth2 authorization flow manually."""
    print("=" * 70)
    print("Gmail OAuth2 Manual Authorization")
    print("=" * 70)
    print()

    # Check if credentials file exists
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"❌ ERROR: OAuth2 credentials file not found!")
        print(f"   Expected: {CREDENTIALS_PATH}")
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
            print("=" * 70)
            print("MANUAL AUTHORIZATION REQUIRED")
            print("=" * 70)
            print()

            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )

            # Generate authorization URL
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )

            print("📋 STEP 1: Copy this URL and paste it in your browser:")
            print()
            print(auth_url)
            print()
            print("=" * 70)
            print()
            print("📋 STEP 2: Login and authorize the application")
            print()
            print("   In the browser:")
            print("   1. Login with your Gmail account")
            print("   2. You may see 'Google hasn't verified this app'")
            print("      - Click 'Advanced'")
            print("      - Click 'Go to Claims Data Entry Agent (unsafe)'")
            print("   3. Review and click 'Allow' for all permissions")
            print()
            print("=" * 70)
            print()

            # Get authorization code from user
            auth_code = input("📋 STEP 3: Paste the authorization code here: ").strip()

            # Exchange code for credentials
            print()
            print("Exchanging authorization code for credentials...")
            flow.fetch_token(code=auth_code)
            creds = flow.credentials

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
    print("=" * 70)
    print("✅ Gmail OAuth2 setup complete!")
    print("=" * 70)
    print()
    print("You can now run the application:")
    print("  docker-compose up -d")
    print()


if __name__ == "__main__":
    main()
