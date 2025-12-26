#!/usr/bin/env python3
"""
Test processing a SINGLE email with REAL OCR extraction.
Minimal API calls to avoid rate limits.
"""

import asyncio
import json
import base64
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Import OCR service
from src.services.ocr_service import OCRService
from src.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


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
    print("📧 Checking Unread Emails with Attachments")
    print("=" * 70)
    print()

    try:
        service = get_gmail_service()

        # Get unread messages with attachments
        results = service.users().messages().list(
            userId='me',
            q='is:unread has:attachment',
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

        print(f"✅ Downloaded: {filename} ({len(file_data):,} bytes)")
        return filepath

    except Exception as e:
        print(f"❌ Download failed: {e}")
        return None


async def process_single_email(email_id):
    """Process a single email with REAL OCR extraction."""
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
            print(f"  - {att['filename']} ({att['mime_type']}, {att['size']:,} bytes)")
        print()

        # Process first image attachment
        image_attachment = None
        for att in attachments:
            if att['mime_type'].startswith('image/'):
                image_attachment = att
                break

        if not image_attachment:
            print("⚠️  No image attachments found (OCR requires images)")
            return

        print(f"Processing: {image_attachment['filename']}")
        print()

        # Download attachment
        filepath = await download_attachment(
            email_id,
            image_attachment['attachment_id'],
            image_attachment['filename']
        )

        if not filepath:
            return

        # ========== REAL OCR PROCESSING ==========
        print()
        print("=" * 70)
        print("🔍 Running OCR Extraction (PaddleOCR-VL)")
        print("=" * 70)
        print()
        print("⏳ Initializing OCR engine...")

        ocr_service = OCRService()

        print("⏳ Processing image... (this may take 10-30 seconds)")
        print()

        # Extract claim data
        extraction = await ocr_service.extract_structured_data(str(filepath))

        # Display results
        print("=" * 70)
        print("✅ OCR Extraction Complete!")
        print("=" * 70)
        print()
        print(f"📊 Confidence Score: {extraction.confidence_score * 100:.1f}%")
        print()
        print("📝 Extracted Data:")
        print(f"  Member ID: {extraction.claim.member_id or 'N/A'}")
        print(f"  Member Name: {extraction.claim.member_name or 'N/A'}")
        print(f"  Policy Number: {extraction.claim.policy_number or extraction.claim.member_id or 'N/A'}")
        print(f"  Provider: {extraction.claim.provider_name or 'N/A'}")
        print(f"  Service Date: {extraction.claim.service_date or 'N/A'}")
        print(f"  Receipt Number: {extraction.claim.receipt_number or 'N/A'}")
        print(f"  Total Amount: RM {(extraction.claim.total_amount or 0.00):.2f}")
        print()

        if extraction.claim.itemized_charges:
            print(f"  Itemized Charges ({len(extraction.claim.itemized_charges)} items):")
            for item in extraction.claim.itemized_charges[:5]:  # Show first 5
                print(f"    - {item.get('description', 'N/A')}: RM {item.get('amount', 0):.2f}")
            if len(extraction.claim.itemized_charges) > 5:
                print(f"    ... and {len(extraction.claim.itemized_charges) - 5} more items")
            print()

        # Determine routing based on confidence
        if extraction.confidence_score >= 0.90:
            status = "✅ HIGH CONFIDENCE - Auto-submit ready"
        elif extraction.confidence_score >= 0.75:
            status = "⚠️  MEDIUM CONFIDENCE - Review recommended"
        else:
            status = "❌ LOW CONFIDENCE - Manual review required"
        print(f"🎯 Status: {status}")
        print()

        # Generate NCB JSON format
        print("=" * 70)
        print("📄 Generating NCB JSON")
        print("=" * 70)
        print()

        claim_data = {
            "Event date": extraction.claim.service_date.isoformat() if extraction.claim.service_date else datetime.now().date().isoformat(),
            "Submission Date": datetime.now().isoformat(),
            "Claim Amount": float(extraction.claim.total_amount or 0.0),
            "Invoice Number": extraction.claim.receipt_number or "UNKNOWN",
            "Policy Number": extraction.claim.policy_number or extraction.claim.member_id or "UNKNOWN",
            # Metadata
            "source_email_id": email_id,
            "source_filename": image_attachment['filename'],
            "extraction_confidence": extraction.confidence_score,
            "extraction_timestamp": datetime.now().isoformat(),
            # Optional fields
            "provider_name": extraction.claim.provider_name,
            "member_name": extraction.claim.member_name,
            "member_id": extraction.claim.member_id,
            "itemized_charges": extraction.claim.itemized_charges or [],
        }

        # Save JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"claim_ocr_{timestamp}.json"
        json_dir = Path('/app/data/json_output')
        json_dir.mkdir(parents=True, exist_ok=True)
        json_filepath = json_dir / json_filename

        with open(json_filepath, 'w') as f:
            json.dump(claim_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Generated: {json_filename}")
        print(f"   Location: {json_filepath}")
        print()

        # Upload to Drive
        print("=" * 70)
        print("☁️  Uploading to Google Drive")
        print("=" * 70)
        print()

        drive_service = get_drive_service()

        file_metadata = {
            'name': json_filename,
            'parents': ['1VTCmsZzfr7BErVTVvcAP-gbjVhl6Afmz']  # Claims Archive
        }

        media = MediaFileUpload(str(json_filepath), mimetype='application/json')
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,name,webViewLink'
        ).execute()

        print(f"✅ Uploaded to Drive: Claims Archive")
        print(f"   File ID: {file['id']}")
        print(f"   File Name: {file['name']}")
        print(f"   Link: {file.get('webViewLink', 'N/A')}")
        print()

        # Summary
        print("=" * 70)
        print("✅ PROCESSING COMPLETE!")
        print("=" * 70)
        print()
        print(f"📧 Email: {headers.get('Subject', 'N/A')}")
        print(f"📎 Attachment: {image_attachment['filename']}")
        print(f"💰 Amount: RM {(extraction.claim.total_amount or 0.00):.2f}")
        print(f"📊 Confidence: {extraction.confidence_score * 100:.1f}%")
        print(f"📄 JSON: {json_filename}")
        print(f"☁️  Drive: Uploaded")
        print()

        # Cleanup
        if filepath.exists():
            filepath.unlink()
            print("🧹 Cleaned up temporary files")
        print()

    except Exception as e:
        print(f"❌ Error processing email: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main entry point."""
    print()
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║         SINGLE EMAIL TEST WITH REAL OCR EXTRACTION               ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print("This script will:")
    print("  1. List unread emails with attachments (max 5)")
    print("  2. Let you choose ONE email to process")
    print("  3. Download image attachment")
    print("  4. Run PaddleOCR-VL extraction")
    print("  5. Generate NCB JSON with real data")
    print("  6. Upload to Google Drive")
    print()
    print("⚠️  OCR processing takes 10-30 seconds per image")
    print("⚠️  Minimal API calls to avoid rate limits")
    print()

    # Step 1: List emails
    emails = await list_unread_emails(max_results=5)

    if not emails:
        print("No unread emails with attachments found.")
        return

    # Step 2: Choose email (auto-select first for demo)
    print("=" * 70)
    print("Which email do you want to process?")
    print()
    print("Enter email number (1-{}) or 'q' to quit: ".format(len(emails)), end='')

    # Default to first email
    choice = '1'
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

        # Step 3: Process email with OCR
        await process_single_email(selected_email['id'])

    except ValueError:
        print("❌ Invalid input")


if __name__ == "__main__":
    asyncio.run(main())
