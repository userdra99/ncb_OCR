#!/usr/bin/env python3
"""
Generate Gmail OAuth token with Pub/Sub scope.
Run this on the host machine (not inside Docker) to generate secrets/gmail_token.json
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path

# OAuth scopes including Pub/Sub
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/pubsub",  # Required for Gmail Watch + Pub/Sub
]

def main():
    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    credentials_path = project_root / "secrets" / "gmail-oauth-credentials.json"
    token_path = project_root / "secrets" / "gmail_token.json"

    print(f"📁 Using credentials: {credentials_path}")
    print(f"📁 Will save token to: {token_path}")

    if not credentials_path.exists():
        print(f"❌ ERROR: Credentials file not found at {credentials_path}")
        print("   Please ensure gmail_credentials.json exists in the secrets/ directory")
        return 1

    print("\n🔐 Starting OAuth flow...")
    print("   A browser window will open for authorization")
    print("   Please approve all requested permissions (including Pub/Sub)")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path),
            SCOPES
        )

        creds = flow.run_local_server(port=0)

        # Save token
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())

        print(f"\n✅ SUCCESS! Token saved to {token_path}")
        print("\n📋 Token includes the following scopes:")
        for scope in creds.scopes:
            print(f"   ✓ {scope}")

        print("\n🚀 Next steps:")
        print("   1. Restart the Docker container:")
        print("      docker compose restart app")
        print("   2. Check logs for successful worker startup:")
        print("      docker compose logs app -f | grep -E '(watch|listener|worker)'")

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
