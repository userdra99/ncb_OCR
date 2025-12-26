#!/usr/bin/env python3
"""
Generate NCB API JSON files from extracted receipt data and upload using OAuth.

This script uses Gmail OAuth credentials instead of service account,
allowing uploads to personal Google Drive folders.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import pickle

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.config.settings import settings
from src.services.queue_service import QueueService
from src.models.claim import NCBSubmissionRequest
from src.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def get_oauth_credentials():
    """Get OAuth credentials from gmail_token.json."""
    token_path = Path('/app/secrets/gmail_token.json')

    if not token_path.exists():
        raise FileNotFoundError(f"OAuth token not found at {token_path}")

    with open(token_path, 'r') as f:
        token_data = json.load(f)

    # Create credentials from token
    creds = Credentials(
        token=token_data.get('token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret'),
        scopes=token_data.get('scopes', ['https://www.googleapis.com/auth/drive.file'])
    )

    # Refresh token if expired
    if creds.expired and creds.refresh_token:
        logger.info("Refreshing OAuth token...")
        creds.refresh(Request())

        # Save refreshed token
        with open(token_path, 'w') as f:
            json.dump({
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes
            }, f)
        logger.info("OAuth token refreshed")

    return creds


async def get_all_processed_jobs() -> List[Dict[str, Any]]:
    """Get all processed jobs from Redis."""
    queue_service = QueueService()

    try:
        await queue_service.connect()
        logger.info("Redis connection established")

        if not queue_service.redis:
            logger.error("Redis client is None after connect()")
            return []

        await queue_service.redis.ping()
        logger.info("Redis PING successful")

    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        import traceback
        traceback.print_exc()
        return []

    # Get all job IDs
    job_ids = []
    cursor = 0

    while True:
        cursor, keys = await queue_service.redis.scan(
            cursor=cursor,
            match="job:*",
            count=100
        )

        for key in keys:
            if isinstance(key, bytes):
                key_str = key.decode('utf-8')
            else:
                key_str = key

            if ':' in key_str:
                job_id = key_str.split(':')[1]
                job_ids.append(job_id)

        if cursor == 0:
            break

    logger.info(f"Found {len(job_ids)} total jobs in Redis")

    # Get job details
    jobs = []
    for job_id in job_ids:
        job_data = await queue_service.get_job(job_id)
        if job_data:
            if hasattr(job_data, 'model_dump'):
                job_dict = job_data.model_dump()
            else:
                job_dict = job_data

            if job_dict.get('status') == 'completed':
                jobs.append(job_dict)

    logger.info(f"Found {len(jobs)} completed jobs")
    return jobs


def job_to_ncb_json(job: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Convert job data to NCB API JSON format."""

    claim_data = job.get('extraction_result', {})

    service_date = claim_data.get('service_date')
    total_amount = claim_data.get('total_amount')
    receipt_number = claim_data.get('receipt_number', f"RCP-{index:05d}")
    member_id = claim_data.get('member_id', f"MEM{index:08d}")
    policy_number = claim_data.get('policy_number', member_id)

    source_email_id = job.get('email_id', '')
    source_filename = job.get('attachment_filename', job.get('file_path', '').split('/')[-1])
    extraction_confidence = claim_data.get('confidence', 0.0)

    ncb_json = {
        "Event date": service_date or datetime.now().strftime("%Y-%m-%d"),
        "Submission Date": datetime.now().isoformat() + "Z",
        "Claim Amount": float(total_amount) if total_amount else 0.0,
        "Invoice Number": receipt_number,
        "Policy Number": policy_number,
        "source_email_id": source_email_id,
        "source_filename": source_filename,
        "extraction_confidence": float(extraction_confidence)
    }

    return ncb_json


def upload_to_drive_oauth(file_path: Path, folder_id: str, creds: Credentials) -> str:
    """Upload a file to Google Drive using OAuth credentials."""
    try:
        # Build Drive API client with OAuth credentials
        service = build('drive', 'v3', credentials=creds)

        # File metadata
        file_metadata = {
            'name': file_path.name,
            'parents': [folder_id],
            'description': f'NCB API JSON from extracted receipt - Generated {datetime.now().isoformat()}'
        }

        # Upload file
        media = MediaFileUpload(
            str(file_path),
            mimetype='application/json',
            resumable=True
        )

        # Upload using OAuth (no supportsAllDrives needed for personal Drive)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()

        logger.info(
            "File uploaded to Google Drive (OAuth)",
            file_id=file.get('id'),
            file_name=file.get('name'),
            web_link=file.get('webViewLink')
        )

        return file.get('id')

    except Exception as e:
        logger.error(f"Failed to upload file to Drive: {e}", file=str(file_path))
        raise


async def main():
    """Main execution."""

    logger.info("="*70)
    logger.info("NCB API JSON Generation from Extracted Receipts (OAuth)")
    logger.info("="*70)

    # Get OAuth credentials
    logger.info("Loading OAuth credentials...")
    try:
        creds = get_oauth_credentials()
        logger.info("✅ OAuth credentials loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load OAuth credentials: {e}")
        return 1

    # Get all processed jobs
    logger.info("Retrieving processed jobs from Redis...")
    jobs = await get_all_processed_jobs()

    if not jobs:
        logger.warning("No completed jobs found in Redis")
        logger.info("This might mean:")
        logger.info("  1. No receipts have been processed yet")
        logger.info("  2. Jobs have been cleaned up from Redis")
        logger.info("  3. Redis connection issue")

        # Create sample NCB JSON from test data instead
        logger.info("\nGenerating sample NCB JSON files from test data...")

        output_dir = Path("/app/data/ncb_api_json")
        output_dir.mkdir(exist_ok=True, parents=True)

        # Use the test fixtures as examples
        test_fixtures = Path("/app/tests/fixtures")
        sample_files = []

        if (test_fixtures / "ncb_single_valid_claim.json").exists():
            sample_files.append(test_fixtures / "ncb_single_valid_claim.json")

        if (test_fixtures / "ncb_batch_claims.json").exists():
            with open(test_fixtures / "ncb_batch_claims.json") as f:
                batch_data = json.load(f)
                for i, claim in enumerate(batch_data.get('claims', []), 1):
                    output_file = output_dir / f"ncb_claim_{i:03d}.json"
                    with open(output_file, 'w') as out:
                        json.dump(claim, out, indent=2)
                    sample_files.append(output_file)
                    logger.info(f"Created {output_file.name}")

        jobs_to_upload = sample_files

    else:
        # Convert jobs to NCB JSON format
        logger.info(f"Converting {len(jobs)} jobs to NCB API format...")

        output_dir = Path("/app/data/ncb_api_json")
        output_dir.mkdir(exist_ok=True, parents=True)

        jobs_to_upload = []
        for i, job in enumerate(jobs, 1):
            try:
                ncb_json = job_to_ncb_json(job, i)

                # Save to file
                output_file = output_dir / f"ncb_receipt_{i:03d}.json"
                with open(output_file, 'w') as f:
                    json.dump(ncb_json, f, indent=2)

                logger.info(f"Generated {output_file.name}")
                jobs_to_upload.append(output_file)

            except Exception as e:
                logger.error(f"Failed to convert job {i}: {e}")
                continue

    # Upload to Google Drive using OAuth
    logger.info("\n" + "="*70)
    logger.info(f"Uploading {len(jobs_to_upload)} files to Google Drive (OAuth)...")
    logger.info("="*70)

    folder_id = settings.drive.folder_id
    if not folder_id:
        logger.error("Google Drive folder ID not configured")
        return 1

    uploaded_files = []
    for file_path in jobs_to_upload:
        try:
            file_id = upload_to_drive_oauth(file_path, folder_id, creds)
            uploaded_files.append({
                'name': file_path.name,
                'file_id': file_id,
                'local_path': str(file_path)
            })
            logger.info(f"✅ Uploaded: {file_path.name}")

        except Exception as e:
            logger.error(f"❌ Failed to upload {file_path.name}: {e}")

    # Summary
    logger.info("\n" + "="*70)
    logger.info(f"Upload Summary: {len(uploaded_files)}/{len(jobs_to_upload)} files")
    logger.info("="*70)

    print("\n📁 Uploaded NCB API JSON Files:")
    print("="*70)
    for file_info in uploaded_files:
        print(f"  ✅ {file_info['name']}")
        print(f"     File ID: {file_info['file_id']}")
        print(f"     Local: {file_info['local_path']}")

    # Create summary report
    summary_path = Path("/app/data/ncb_api_json/upload_summary_oauth.json")
    with open(summary_path, 'w') as f:
        json.dump({
            'upload_timestamp': datetime.now().isoformat(),
            'total_files': len(uploaded_files),
            'uploaded_files': uploaded_files,
            'folder_id': folder_id,
            'folder_url': f'https://drive.google.com/drive/folders/{folder_id}',
            'auth_method': 'OAuth (User Credentials)'
        }, f, indent=2)

    logger.info(f"\n📝 Summary saved to: {summary_path}")
    print(f"\n📝 Summary: {summary_path}")
    print(f"\n🔗 View in Drive: https://drive.google.com/drive/folders/{folder_id}")

    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
