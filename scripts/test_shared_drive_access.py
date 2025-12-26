#!/usr/bin/env python3
"""Test Google Shared Drive access for service account.

This script verifies that the service account can:
1. Access the configured Shared Drive
2. List files in the Shared Drive
3. Create a test file
4. Delete the test file

Usage:
    python scripts/test_shared_drive_access.py [credentials_path] [folder_id]
    
    If not provided, reads from environment variables:
    - DRIVE_CREDENTIALS_PATH
    - DRIVE_FOLDER_ID
"""

import sys
import os
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import tempfile
import datetime


def get_config():
    """Get configuration from args or environment."""
    
    # Try command line arguments first
    if len(sys.argv) >= 3:
        creds_path = sys.argv[1]
        folder_id = sys.argv[2]
    else:
        # Fall back to environment variables
        creds_path = os.getenv('DRIVE_CREDENTIALS_PATH')
        folder_id = os.getenv('DRIVE_FOLDER_ID')
    
    # Validate
    if not creds_path:
        print("❌ Error: DRIVE_CREDENTIALS_PATH not provided")
        print("\nUsage:")
        print("  python scripts/test_shared_drive_access.py [credentials_path] [folder_id]")
        print("\nOr set environment variables:")
        print("  export DRIVE_CREDENTIALS_PATH=/path/to/credentials.json")
        print("  export DRIVE_FOLDER_ID=your-folder-id")
        sys.exit(1)
    
    if not folder_id:
        print("❌ Error: DRIVE_FOLDER_ID not provided")
        print("\nUsage:")
        print("  python scripts/test_shared_drive_access.py [credentials_path] [folder_id]")
        print("\nOr set environment variables:")
        print("  export DRIVE_CREDENTIALS_PATH=/path/to/credentials.json")
        print("  export DRIVE_FOLDER_ID=your-folder-id")
        sys.exit(1)
    
    # Expand paths
    creds_path = os.path.expanduser(creds_path)
    
    return creds_path, folder_id


def test_shared_drive_access():
    """Test service account access to Google Shared Drive."""

    print("=" * 60)
    print("Google Shared Drive Access Test")
    print("=" * 60)
    print()

    # Load configuration
    creds_path, folder_id = get_config()

    print(f"📁 Drive Folder ID: {folder_id}")
    print(f"🔑 Credentials Path: {creds_path}")
    print()

    # Initialize credentials
    print("⏳ Loading service account credentials...")
    try:
        creds = Credentials.from_service_account_file(
            creds_path,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        print(f"✅ Credentials loaded")
        print(f"   Service Account: {creds.service_account_email}")
        print()
    except Exception as e:
        print(f"❌ Failed to load credentials: {e}")
        return False

    # Build Drive service
    print("⏳ Building Drive API service...")
    try:
        service = build('drive', 'v3', credentials=creds)
        print("✅ Drive service initialized")
        print()
    except Exception as e:
        print(f"❌ Failed to build service: {e}")
        return False

    # Test 1: List files in Shared Drive
    print("📋 Test 1: List files in Shared Drive")
    print("-" * 60)
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, createdTime, size)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=10
        ).execute()

        files = results.get('files', [])
        print(f"✅ Successfully listed files: {len(files)} found")

        if files:
            print("\nExisting files:")
            for file in files[:5]:  # Show first 5
                size = file.get('size', 'N/A')
                created = file.get('createdTime', 'N/A')
                print(f"  - {file['name']}")
                print(f"    ID: {file['id']}")
                print(f"    Size: {size} bytes | Created: {created}")
        else:
            print("  No files found (this is fine for a new Shared Drive)")
        print()
    except Exception as e:
        print(f"❌ Failed to list files: {e}")
        print("\n💡 Possible issues:")
        print("  1. Service account not added to Shared Drive")
        print("  2. Incorrect folder ID")
        print("  3. Insufficient permissions (needs Content Manager role)")
        print()
        return False

    # Test 2: Create a test file
    print("📤 Test 2: Upload test file to Shared Drive")
    print("-" * 60)
    try:
        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            tmp.write(f"Test file created at {datetime.datetime.now().isoformat()}\n")
            tmp.write("This is a test upload from the Claims Data Entry Agent.\n")
            tmp.write("If you see this file, Shared Drive access is working!\n")
            tmp_path = tmp.name

        test_filename = f"test_upload_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        file_metadata = {
            'name': test_filename,
            'parents': [folder_id],
            'description': 'Test file - safe to delete'
        }

        media = MediaFileUpload(
            tmp_path,
            mimetype='text/plain',
            resumable=True
        )

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink',
            supportsAllDrives=True
        ).execute()

        print(f"✅ Successfully uploaded test file")
        print(f"   File ID: {file.get('id')}")
        print(f"   File Name: {file.get('name')}")
        print(f"   View Link: {file.get('webViewLink')}")
        print()

        # Clean up temp file
        Path(tmp_path).unlink()

        # Test 3: Delete the test file
        print("🗑️  Test 3: Delete test file")
        print("-" * 60)

        service.files().delete(
            fileId=file.get('id'),
            supportsAllDrives=True
        ).execute()

        print("✅ Successfully deleted test file")
        print()

    except Exception as e:
        print(f"❌ Failed to upload/delete test file: {e}")
        print("\n💡 Possible issues:")
        print("  1. Service account has insufficient permissions")
        print("  2. Shared Drive is read-only")
        print("  3. Folder ID is incorrect")
        print()
        return False

    # Test 4: Check folder creation capability
    print("📁 Test 4: Create and delete test folder")
    print("-" * 60)
    try:
        test_folder_name = f"test_folder_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

        folder_metadata = {
            'name': test_folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [folder_id]
        }

        folder = service.files().create(
            body=folder_metadata,
            fields='id, name',
            supportsAllDrives=True
        ).execute()

        print(f"✅ Successfully created test folder")
        print(f"   Folder ID: {folder.get('id')}")
        print(f"   Folder Name: {folder.get('name')}")

        # Delete test folder
        service.files().delete(
            fileId=folder.get('id'),
            supportsAllDrives=True
        ).execute()

        print(f"✅ Successfully deleted test folder")
        print()

    except Exception as e:
        print(f"❌ Failed to create/delete folder: {e}")
        print()
        return False

    # All tests passed
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print()
    print("Your Google Shared Drive is configured correctly.")
    print("The service account has the necessary permissions.")
    print("The application can now archive files to Drive.")
    print()

    return True


def print_setup_instructions():
    """Print setup instructions if tests fail."""

    print()
    print("=" * 60)
    print("📖 SETUP INSTRUCTIONS")
    print("=" * 60)
    print()
    print("If the tests failed, follow these steps:")
    print()
    print("1. CREATE SHARED DRIVE:")
    print("   - Go to drive.google.com")
    print("   - Click 'Shared drives' in left sidebar")
    print("   - Click '+ New' to create a new Shared Drive")
    print("   - Name it 'Claims Archive' (or your preferred name)")
    print()
    print("2. GET SHARED DRIVE ID:")
    print("   - Open the Shared Drive you just created")
    print("   - Copy the ID from the URL:")
    print("     https://drive.google.com/drive/folders/0AJKxxxxxxxxxxxxxxx")
    print("     The ID is: 0AJKxxxxxxxxxxxxxxx")
    print()
    print("3. ADD SERVICE ACCOUNT:")
    print("   - Right-click on the Shared Drive → 'Manage members'")
    print("   - Add your service account email (from credentials file)")
    print("   - Set permission to 'Content Manager'")
    print("   - Uncheck 'Notify people' and click 'Send'")
    print()
    print("4. UPDATE .env FILE:")
    print("   - Set DRIVE_FOLDER_ID to your Shared Drive ID")
    print("   - Verify DRIVE_CREDENTIALS_PATH points to your credentials")
    print()
    print("5. RE-RUN THIS TEST:")
    print("   python scripts/test_shared_drive_access.py")
    print()
    print("For detailed instructions, see:")
    print("  docs/GOOGLE_SHARED_DRIVE_SETUP.md")
    print()


if __name__ == '__main__':
    try:
        success = test_shared_drive_access()

        if not success:
            print_setup_instructions()
            sys.exit(1)

        sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
