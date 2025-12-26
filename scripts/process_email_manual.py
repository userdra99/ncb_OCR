#!/usr/bin/env python3
"""
Manual email processing script - bypasses continuous polling.

Usage:
  python scripts/process_email_manual.py <email_id>
  
Get email_id from Gmail web interface URL or use 'list' to see available emails.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.email_service import EmailService
from src.services.queue_service import QueueService
from src.models.job import Job, JobStatus
from src.utils.logging import configure_logging, get_logger
import uuid
from datetime import datetime

configure_logging()
logger = get_logger(__name__)


async def list_emails():
    """List available unread emails."""
    email_service = EmailService()
    
    try:
        emails = await email_service.poll_inbox()
        
        if not emails:
            print("No unread emails with attachments found")
            return
        
        print(f"\nFound {len(emails)} unread email(s):\n")
        for i, email in enumerate(emails, 1):
            print(f"{i}. Email ID: {email.message_id}")
            print(f"   From: {email.sender}")
            print(f"   Subject: {email.subject}")
            print(f"   Attachments: {len(email.attachments)}")
            print()
        
        print("To process an email, run:")
        print(f"  python {sys.argv[0]} <email_id>")
        
    except Exception as e:
        print(f"Error listing emails: {e}")
        if "429" in str(e):
            print("\n⚠️  Gmail API quota exceeded. Wait 24 hours or:")
            print("  1. Check https://console.cloud.google.com/apis/api/gmail.googleapis.com/quotas")
            print("  2. Request quota increase if needed")
        sys.exit(1)


async def process_email(email_id: str):
    """Process a specific email by ID."""
    email_service = EmailService()
    queue_service = QueueService()
    
    await queue_service.connect()
    
    try:
        # Get email details
        print(f"Fetching email {email_id}...")
        email = await email_service.get_email_by_id(email_id)
        
        if not email:
            print(f"Email {email_id} not found")
            return
        
        print(f"\n📧 Processing email from {email.sender}")
        print(f"   Subject: {email.subject}")
        print(f"   Attachments: {len(email.attachments)}\n")
        
        # Download and process each attachment
        for attachment in email.attachments:
            if not attachment.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.pdf')):
                print(f"   ⏭️  Skipping {attachment.filename} (not an image/PDF)")
                continue
            
            print(f"   📎 Processing {attachment.filename}...")
            
            # Download attachment
            local_path = await email_service.download_attachment(email.message_id, attachment)
            
            # Create job
            job = Job(
                id=str(uuid.uuid4()),
                email_id=email.message_id,
                attachment_filename=attachment.filename,
                attachment_path=str(local_path),
                status=JobStatus.PENDING,
                created_at=datetime.now(),
            )
            
            # Enqueue for OCR
            await queue_service.enqueue_job("claims:ocr_queue", job)
            
            print(f"   ✅ Job created: {job.id}")
            print(f"      Queued for OCR processing")
        
        # Mark email as processed
        await email_service.mark_as_processed(email.message_id)
        print(f"\n✅ Email marked as processed")
        
    except Exception as e:
        print(f"Error processing email: {e}")
        sys.exit(1)
    
    finally:
        await queue_service.disconnect()


async def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} list           - List available emails")
        print(f"  {sys.argv[0]} <email_id>     - Process specific email")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        await list_emails()
    else:
        await process_email(command)


if __name__ == "__main__":
    asyncio.run(main())

