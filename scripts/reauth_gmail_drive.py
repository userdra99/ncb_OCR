#!/usr/bin/env python3
"""
Re-authenticate Gmail OAuth with both Gmail and Drive scopes.
Copy-paste method (no localhost required).
"""

import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Include BOTH Gmail and Drive scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive.file",  # Create/modify files
]

CREDENTIALS_PATH = "secrets/gmail-oauth-credentials.json"
TOKEN_PATH = "secrets/gmail_token.json"


def main():
    print("=" * 70)
    print("Gmail + Drive OAuth2 Re-Authorization")
    print("=" * 70)
    print()
    print("This will add Gmail permissions to your OAuth token")
    print("(currently only has Drive access)")
    print()

    # Load client config
    with open(CREDENTIALS_PATH, 'r') as f:
        client_config = json.load(f)

    # Force re-authorization to add Gmail scopes
    print("🔄 Starting new authorization flow...")
    print()

    # Use installed app flow with out-of-band redirect
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri='urn:ietf:wg:oauth:2.0:oob'
    )

    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')

    print("🔗 STEP 1: Open this URL in your browser:\n")
    print(auth_url)
    print()
    print("=" * 70)
    print()
    print("🔐 STEP 2: Login and authorize")
    print()
    print("   - Login with your Gmail (dra.ncbtest@gmail.com)")
    print("   - You may see 'unverified app' warning - click 'Advanced'")
    print("   - Click 'Go to Claims Data Entry Agent (unsafe)'")
    print("   - Click 'Allow' for ALL permissions:")
    print("     ✓ Read Gmail")
    print("     ✓ Modify Gmail")
    print("     ✓ Manage Drive files")
    print("   - Copy the authorization code shown")
    print()
    print("=" * 70)
    print()

    code = input("📋 STEP 3: Paste the authorization code here: ").strip()

    if not code:
        print("❌ No code entered. Exiting.")
        return

    print("\n🔄 Exchanging code for token...")
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Save credentials
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, 'w') as token:
        token.write(creds.to_json())
    print(f"✅ Token saved to: {TOKEN_PATH}")

    # Test Gmail connection
    print("\n🧪 Testing Gmail API connection...")
    try:
        gmail_service = build('gmail', 'v1', credentials=creds)
        profile = gmail_service.users().getProfile(userId='me').execute()
        print(f"✅ Gmail: {profile['emailAddress']}")
        print(f"   Total messages: {profile['messagesTotal']}")
    except Exception as e:
        print(f"❌ Gmail test failed: {e}")

    # Test Drive connection
    print("\n🧪 Testing Drive API connection...")
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        about = drive_service.about().get(fields='user').execute()
        print(f"✅ Drive: {about['user']['emailAddress']}")
    except Exception as e:
        print(f"❌ Drive test failed: {e}")

    print("\n" + "=" * 70)
    print("✅ Re-authorization complete!")
    print("=" * 70)
    print()
    print("You can now:")
    print("  - Read emails from Gmail")
    print("  - Download attachments")
    print("  - Upload files to Drive")
    print()


if __name__ == "__main__":
    main()
