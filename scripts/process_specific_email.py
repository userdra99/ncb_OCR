#!/usr/bin/env python3
"""
Process a specific email by ID with REAL OCR extraction.
"""

import asyncio
import json
import base64
from datetime import datetime
from pathlib import Path
import sys

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


async def process_email(email_id):
    """Process a specific email with REAL OCR extraction."""
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

        # Process first image or PDF attachment
        processable_attachment = None
        for att in attachments:
            mime_type = att['mime_type']
            if mime_type.startswith('image/') or mime_type == 'application/pdf':
                processable_attachment = att
                break

        if not processable_attachment:
            print("⚠️  No image or PDF attachments found (OCR requires images or PDFs)")
            return

        file_type = "PDF" if processable_attachment['mime_type'] == 'application/pdf' else "Image"
        print(f"Processing {file_type}: {processable_attachment['filename']}")
        print()

        # Download attachment
        filepath = await download_attachment(
            email_id,
            processable_attachment['attachment_id'],
            processable_attachment['filename']
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

        processing_msg = "PDF" if file_type == "PDF" else "image"
        print(f"⏳ Processing {processing_msg}... (this may take 10-60 seconds for PDFs)")
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
            "source_filename": processable_attachment['filename'],
            "source_file_type": file_type,
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
        print(f"📎 Attachment: {processable_attachment['filename']} ({file_type})")
        print(f"💰 Amount: RM {(extraction.claim.total_amount or 0.00):.2f}")
        print(f"📊 Confidence: {extraction.confidence_score * 100:.1f}%")
        print(f"📄 JSON: {json_filename}")
        print(f"☁️  Drive: Uploaded")
        if extraction.warnings:
            print(f"⚠️  Warnings: {', '.join(extraction.warnings)}")
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


if __name__ == "__main__":
    email_id = sys.argv[1] if len(sys.argv) > 1 else "19b4e23d43e66fff"  # Default to email #7
    print()
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║         PROCESS SPECIFIC EMAIL WITH OCR EXTRACTION              ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print(f"Processing email ID: {email_id}")
    asyncio.run(process_email(email_id))
