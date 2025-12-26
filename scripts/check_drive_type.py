#!/usr/bin/env python3
"""Check if a Drive folder is a Shared Drive or personal Drive."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from src.config.settings import settings

def check_drive_type():
    """Check if folder is Shared Drive or personal Drive."""

    # Load credentials
    creds = Credentials.from_service_account_file(
        settings.drive.credentials_path,
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )

    service = build('drive', 'v3', credentials=creds)
    folder_id = settings.drive.folder_id

    print(f"Checking folder ID: {folder_id}")
    print("=" * 70)

    try:
        # Try to get folder info with supportsAllDrives
        file_info = service.files().get(
            fileId=folder_id,
            fields='id, name, driveId, parents',
            supportsAllDrives=True
        ).execute()

        print(f"✅ Folder found: {file_info.get('name')}")
        print(f"   ID: {file_info.get('id')}")

        if file_info.get('driveId'):
            print(f"\n✅ This IS a Shared Drive folder")
            print(f"   Shared Drive ID: {file_info.get('driveId')}")
            print(f"\n   Service accounts CAN upload here! ✅")
        else:
            print(f"\n❌ This is a PERSONAL Drive folder")
            print(f"   Parents: {file_info.get('parents')}")
            print(f"\n   ⚠️  Service accounts CANNOT upload to personal Drive!")
            print(f"\n   Solution: Create a Shared Drive and update DRIVE_FOLDER_ID")

    except Exception as e:
        print(f"❌ Error checking folder: {e}")

        # Try listing shared drives
        print(f"\n🔍 Listing available Shared Drives...")
        try:
            drives_result = service.drives().list(
                pageSize=10,
                fields='drives(id, name)'
            ).execute()

            drives = drives_result.get('drives', [])
            if drives:
                print(f"\n✅ Found {len(drives)} Shared Drives accessible to this service account:")
                for drive in drives:
                    print(f"   • {drive['name']}")
                    print(f"     ID: {drive['id']}")
            else:
                print(f"\n❌ No Shared Drives found accessible to this service account")
                print(f"\n   You need to:")
                print(f"   1. Create a Shared Drive at drive.google.com")
                print(f"   2. Add service account as member (Content Manager role)")
                print(f"   3. Update DRIVE_FOLDER_ID in .env")

        except Exception as e2:
            print(f"❌ Error listing Shared Drives: {e2}")

if __name__ == '__main__':
    check_drive_type()
