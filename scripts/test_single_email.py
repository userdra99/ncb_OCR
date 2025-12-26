#!/usr/bin/env python3
"""
Safely test processing a SINGLE email with attachment.
Minimal API calls to avoid rate limits.
"""

import asyncio
import json
import base64
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Try to import from src (if in container)
try:
    from src.services.ocr_service import OCRService
    from src.services.drive_service import DriveService
    from src.utils.logging import configure_logging, get_logger
    configure_logging()
    logger = get_logger(__name__)
    IN_CONTAINER = True
except ImportError:
    IN_CONTAINER = False
    print("⚠️  Running outside container - limited functionality")


def get_gmail_service():
    """Get Gmail service with OAuth."""
    with open('/app/secrets/gmail_token.json', 'r') as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data['token'],
        refresh_token=token_data.get('refresh_token'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret')
    )

    return build('gmail', 'v1', credentials=creds)


def get_drive_service():
    """Get Drive service with OAuth."""
    with open('/app/secrets/gmail_token.json', 'r') as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data['token'],
        refresh_token=token_data.get('refresh_token'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret')
    )

    return build('drive', 'v3', credentials=creds)


async def list_unread_emails(max_results=5):
    """List unread emails (minimal API call)."""
    print("=" * 70)
    print("📧 Checking Unread Emails")
    print("=" * 70)
    print()

    try:
        service = get_gmail_service()

        # Get unread messages
        results = service.users().messages().list(
            userId='me',
            q='is:unread has:attachment',  # Only emails with attachments
            maxResults=max_results
        ).execute()

        messages = results.get('messages', [])
        print(f"Found {len(messages)} unread emails with attachments")
        print()

        # Show details of each
        email_list = []
        for idx, msg in enumerate(messages, 1):
            email_data = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()

            headers = {h['name']: h['value'] for h in email_data['payload']['headers']}

            email_info = {
                'index': idx,
                'id': msg['id'],
                'from': headers.get('From', 'N/A'),
                'subject': headers.get('Subject', 'N/A'),
                'date': headers.get('Date', 'N/A')
            }
            email_list.append(email_info)

            print(f"[{idx}] Email ID: {msg['id']}")
            print(f"    From: {email_info['from']}")
            print(f"    Subject: {email_info['subject']}")
            print(f"    Date: {email_info['date']}")
            print()

        return email_list

    except Exception as e:
        print(f"❌ Error: {e}")
        return []


async def download_attachment(message_id, attachment_id, filename):
    """Download a single attachment."""
    try:
        service = get_gmail_service()

        attachment = service.users().messages().attachments().get(
            userId='me',
            messageId=message_id,
            id=attachment_id
        ).execute()

        file_data = base64.urlsafe_b64decode(attachment['data'])

        # Save to temp directory
        output_dir = Path('/app/data/temp')
        output_dir.mkdir(parents=True, exist_ok=True)

        filepath = output_dir / filename
        with open(filepath, 'wb') as f:
            f.write(file_data)

        print(f"✅ Downloaded: {filename} ({len(file_data)} bytes)")
        return filepath

    except Exception as e:
        print(f"❌ Download failed: {e}")
        return None


async def process_single_email(email_id):
    """Process a single email with attachment."""
    print()
    print("=" * 70)
    print(f"📨 Processing Email: {email_id}")
    print("=" * 70)
    print()

    try:
        service = get_gmail_service()

        # Get full email
        message = service.users().messages().get(
            userId='me',
            id=email_id,
            format='full'
        ).execute()

        # Extract headers
        headers = {h['name']: h['value'] for h in message['payload']['headers']}
        print(f"From: {headers.get('From')}")
        print(f"Subject: {headers.get('Subject')}")
        print()

        # Find attachments
        attachments = []
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                if part.get('filename'):
                    attachments.append({
                        'filename': part['filename'],
                        'attachment_id': part['body'].get('attachmentId'),
                        'mime_type': part.get('mimeType'),
                        'size': part['body'].get('size', 0)
                    })

        if not attachments:
            print("⚠️  No attachments found")
            return

        print(f"Found {len(attachments)} attachment(s):")
        for att in attachments:
            print(f"  - {att['filename']} ({att['mime_type']}, {att['size']} bytes)")
        print()

        # Process first attachment only
        first_attachment = attachments[0]
        print(f"Processing: {first_attachment['filename']}")
        print()

        # Download attachment
        filepath = await download_attachment(
            email_id,
            first_attachment['attachment_id'],
            first_attachment['filename']
        )

        if not filepath:
            return

        # Generate mock extraction data (skip OCR for now to save time)
        print("Generating claim data...")

        claim_data = {
            "Event date": datetime.now().date().isoformat(),
            "Submission Date": datetime.now().isoformat(),
            "Claim Amount": 0.0,  # Would come from OCR
            "Invoice Number": "MANUAL-TEST-001",
            "Policy Number": "TEST-POLICY-123",
            "source_email_id": email_id,
            "source_filename": first_attachment['filename'],
            "extraction_confidence": 0.00,  # Manual test
            "provider_name": "Test Provider (Manual)",
            "member_name": "Test Member",
            "note": "⚠️ This is a manual test - no actual OCR performed"
        }

        # Save JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"email_test_{timestamp}.json"
        json_dir = Path('/app/data/json_output')
        json_dir.mkdir(parents=True, exist_ok=True)
        json_filepath = json_dir / json_filename

        with open(json_filepath, 'w') as f:
            json.dump(claim_data, f, indent=2)

        print(f"✅ Generated: {json_filename}")
        print()

        # Upload to Drive
        print("Uploading to Google Drive...")
        drive_service = get_drive_service()

        from googleapiclient.http import MediaFileUpload
        file_metadata = {
            'name': json_filename,
            'parents': ['1VTCmsZzfr7BErVTVvcAP-gbjVhl6Afmz']  # Claims Archive
        }

        media = MediaFileUpload(str(json_filepath), mimetype='application/json')
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,webViewLink'
        ).execute()

        print(f"✅ Uploaded to Drive")
        print(f"   File ID: {file['id']}")
        print(f"   Link: {file.get('webViewLink', 'N/A')}")
        print()

        print("=" * 70)
        print("✅ Processing Complete!")
        print("=" * 70)

    except Exception as e:
        print(f"❌ Error processing email: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main entry point."""
    print()
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║              SAFE SINGLE EMAIL TEST                              ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print("This script will:")
    print("  1. List unread emails with attachments (max 5)")
    print("  2. Let you choose ONE email to process")
    print("  3. Download attachment, generate JSON, upload to Drive")
    print("  4. Minimal API calls to avoid rate limits")
    print()

    # Step 1: List emails
    emails = await list_unread_emails(max_results=5)

    if not emails:
        print("No unread emails with attachments found.")
        return

    # Step 2: Choose email
    print("=" * 70)
    print("Which email do you want to process?")
    print()
    print("Enter email number (1-{}) or 'q' to quit: ".format(len(emails)), end='')

    # For automated testing, default to first email
    # In interactive mode, this would wait for input
    choice = '1'  # Default to first email
    print(choice)
    print()

    if choice.lower() == 'q':
        print("Cancelled.")
        return

    try:
        email_idx = int(choice) - 1
        if email_idx < 0 or email_idx >= len(emails):
            print("❌ Invalid selection")
            return

        selected_email = emails[email_idx]
        print(f"Selected: {selected_email['subject']}")
        print()

        # Step 3: Process email
        await process_single_email(selected_email['id'])

    except ValueError:
        print("❌ Invalid input")


if __name__ == "__main__":
    asyncio.run(main())
