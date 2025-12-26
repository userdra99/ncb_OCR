#!/usr/bin/env python3
"""
Re-authorize Google OAuth with Drive scope added.

This script will prompt you to authorize access to both Gmail and Google Drive
using the same OAuth token. Run this once to add Drive access to your existing
Gmail OAuth credentials.

Usage:
    python scripts/reauthorize_google_oauth.py [credentials_path] [token_path]
    
    Or set environment variables:
    export GMAIL_CREDENTIALS_PATH=/path/to/credentials.json
    export GMAIL_TOKEN_PATH=/path/to/token.json
"""

import sys
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

# All required scopes for Gmail + Drive
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/drive.file",  # Drive access
]


def get_config():
    """Get configuration from args or environment."""
    
    # Try command line arguments first
    if len(sys.argv) >= 3:
        creds_path = sys.argv[1]
        token_path = sys.argv[2]
    else:
        # Fall back to environment variables
        creds_path = os.getenv('GMAIL_CREDENTIALS_PATH')
        token_path = os.getenv('GMAIL_TOKEN_PATH')
    
    # Defaults if not provided
    if not creds_path:
        creds_path = 'secrets/gmail-oauth-credentials.json'
    if not token_path:
        token_path = 'secrets/gmail_token.json'
    
    # Expand paths
    creds_path = Path(creds_path).expanduser()
    token_path = Path(token_path).expanduser()
    
    return creds_path, token_path


def main():
    """Run OAuth authorization flow."""

    creds_path, token_path = get_config()

    print("=" * 60)
    print("Google OAuth Re-authorization")
    print("=" * 60)
    print()
    print("This will authorize access to:")
    print("  ✓ Gmail (read, modify, labels)")
    print("  ✓ Google Drive (file upload)")
    print()
    print("Using credentials from:")
    print(f"  {creds_path}")
    print()
    
    if not creds_path.exists():
        print(f"❌ Error: Credentials file not found at {creds_path}")
        print()
        print("To create OAuth credentials:")
        print("1. Go to https://console.cloud.google.com")
        print("2. Enable Gmail API and Drive API")
        print("3. Create OAuth 2.0 Client ID (Desktop app)")
        print("4. Download credentials JSON")
        print("5. Save as:", creds_path)
        print()
        return False
    
    print("Token will be saved to:")
    print(f"  {token_path}")
    print()

    input("Press ENTER to open browser for authorization...")

    # Run OAuth flow
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(creds_path),
            SCOPES
        )

        creds = flow.run_local_server(port=0)

        # Save token
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())

        print()
        print("=" * 60)
        print("✅ Authorization successful!")
        print("=" * 60)
        print()
        print("Token saved to:", token_path)
        print()
        print("Granted scopes:")
        for scope in SCOPES:
            print(f"  ✓ {scope}")
        print()
        print("You can now use both Gmail and Google Drive services.")
        print()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Authorization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Authorization cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
