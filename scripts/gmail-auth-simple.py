#!/usr/bin/env python3
"""
Simplified Gmail OAuth2 Authorization using out-of-band flow.
This uses copy-paste method instead of localhost redirect.
"""

import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

CREDENTIALS_PATH = "secrets/gmail-oauth-credentials.json"
TOKEN_PATH = "secrets/gmail_token.json"


def main():
    print("=" * 70)
    print("Gmail OAuth2 Authorization (Copy-Paste Method)")
    print("=" * 70)
    print()

    # Load client config
    with open(CREDENTIALS_PATH, 'r') as f:
        client_config = json.load(f)

    # Check if we already have a token
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing token...")
            creds.refresh(Request())
        else:
            # Use installed app flow with out-of-band redirect
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )

            auth_url, _ = flow.authorization_url(prompt='consent')

            print("🔗 STEP 1: Open this URL in your browser:\n")
            print(auth_url)
            print()
            print("=" * 70)
            print()
            print("🔐 STEP 2: Login and authorize")
            print()
            print("   - Login with your Gmail")
            print("   - Click 'Advanced' if you see unverified app warning")
            print("   - Click 'Go to Claims Data Entry Agent (unsafe)'")
            print("   - Click 'Allow' for all permissions")
            print("   - Copy the authorization code shown")
            print()
            print("=" * 70)
            print()

            code = input("📋 STEP 3: Paste the authorization code here: ").strip()

            flow.fetch_token(code=code)
            creds = flow.credentials

        # Save credentials
        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
        print(f"\n✅ Token saved to: {TOKEN_PATH}")

    # Test connection
    print("\n🧪 Testing Gmail API connection...")
    try:
        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()

        print(f"\n✅ Successfully connected!")
        print(f"   Email: {profile['emailAddress']}")
        print(f"   Messages: {profile.get('messagesTotal', 0):,}")
        print()
        print("=" * 70)
        print("✅ Setup complete! You can now run: docker-compose up -d")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
