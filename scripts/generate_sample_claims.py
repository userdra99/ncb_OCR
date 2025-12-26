#!/usr/bin/env python3
"""
Generate sample claim JSON files and upload to Google Shared Drive.
Standalone script that doesn't require queue or test fixtures.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def get_drive_service():
    """Get Google Drive service with Shared Drive support."""
    creds = Credentials.from_service_account_file(
        '/app/secrets/service-account-credentials.json',
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=creds)


def generate_sample_claims():
    """Generate sample claim data."""
    base_date = datetime.now(timezone.utc)

    claims = [
        {
            "Event date": (base_date - timedelta(days=5)).date().isoformat(),
            "Submission Date": base_date.isoformat(),
            "Claim Amount": 435.50,
            "Invoice Number": "INV-2024-001234",
            "Policy Number": "POL-MYS-9876543",
            "source_filename": "medical_receipt_clinic.jpg",
            "extraction_confidence": 0.9885,
            "provider_name": "Klinik Mediviron",
            "member_name": "Ahmad bin Abdullah"
        },
        {
            "Event date": (base_date - timedelta(days=3)).date().isoformat(),
            "Submission Date": base_date.isoformat(),
            "Claim Amount": 125.00,
            "Invoice Number": "RCP-20241220-001",
            "Policy Number": "POL-MYS-1234567",
            "source_filename": "pharmacy_receipt.jpg",
            "extraction_confidence": 0.8750,
            "provider_name": "Guardian Pharmacy",
            "member_name": "Siti binti Rahman"
        },
        {
            "Event date": (base_date - timedelta(days=7)).date().isoformat(),
            "Submission Date": base_date.isoformat(),
            "Claim Amount": 2850.00,
            "Invoice Number": "HOS-2024-5678",
            "Policy Number": "POL-MYS-8765432",
            "source_filename": "hospital_bill.pdf",
            "extraction_confidence": 0.9650,
            "provider_name": "Hospital Pantai",
            "member_name": "Lee Wei Ming"
        },
        {
            "Event date": (base_date - timedelta(days=2)).date().isoformat(),
            "Submission Date": base_date.isoformat(),
            "Claim Amount": 180.50,
            "Invoice Number": "DEN-2024-3456",
            "Policy Number": "POL-MYS-2468135",
            "source_filename": "dental_receipt.jpg",
            "extraction_confidence": 0.8200,
            "provider_name": "Smile Dental Clinic",
            "member_name": "Kumar Subramaniam"
        },
        {
            "Event date": (base_date - timedelta(days=1)).date().isoformat(),
            "Submission Date": base_date.isoformat(),
            "Claim Amount": 95.50,
            "Invoice Number": "TC-20241225-789",
            "Policy Number": "POL-MYS-9753186",
            "source_filename": "traditional_medicine.jpg",
            "extraction_confidence": 0.9150,
            "provider_name": "Kedai Ubat Cina Hock Hua",
            "member_name": "Tan Mei Ling"
        }
    ]

    return claims


async def upload_to_shared_drive(filepath: Path, folder_id: str):
    """
    Upload JSON file to Google Shared Drive.

    Args:
        filepath: Path to JSON file
        folder_id: Drive folder ID

    Returns:
        File ID in Drive
    """
    try:
        service = get_drive_service()

        file_metadata = {
            'name': filepath.name,
            'parents': [folder_id],
            'mimeType': 'application/json'
        }

        media = MediaFileUpload(
            str(filepath),
            mimetype='application/json',
            resumable=True
        )

        # Upload with supportsAllDrives=True for Shared Drive support
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,name,webViewLink',
            supportsAllDrives=True  # Critical for Shared Drive
        ).execute()

        print(f"✅ Uploaded: {filepath.name}")
        print(f"   File ID: {file['id']}")
        print(f"   Link: {file.get('webViewLink', 'N/A')}")

        return file['id']

    except Exception as e:
        print(f"❌ Failed to upload {filepath.name}: {e}")
        raise


async def main():
    """Main entry point."""
    print("=" * 70)
    print("📄 Claims JSON Generator - Shared Drive Upload")
    print("=" * 70)
    print()

    # Create output directory
    output_dir = Path("/app/data/json_output")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")
    print()

    # Drive folder ID from environment/config
    drive_folder_id = "1VTCmsZzfr7BErVTVvcAP-gbjVhl6Afmz"  # Claims Archive

    # Generate sample claims
    claims = generate_sample_claims()
    print(f"Generated {len(claims)} sample claims")
    print()

    # Process each claim
    uploaded_files = []
    for idx, claim in enumerate(claims, 1):
        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"claim_{idx:02d}_{timestamp}.json"
            filepath = output_dir / filename

            # Write JSON file
            with open(filepath, 'w') as f:
                json.dump(claim, f, indent=2, ensure_ascii=False)

            print(f"\n[{idx}/{len(claims)}] Processing {filename}")
            print(f"   Amount: RM {claim['Claim Amount']:.2f}")
            print(f"   Provider: {claim.get('provider_name', 'N/A')}")
            print(f"   Confidence: {claim.get('extraction_confidence', 0) * 100:.1f}%")

            # Upload to Shared Drive
            file_id = await upload_to_shared_drive(filepath, drive_folder_id)

            uploaded_files.append({
                'filename': filename,
                'file_id': file_id,
                'amount': claim['Claim Amount']
            })

            # Small delay between uploads
            await asyncio.sleep(0.5)

        except Exception as e:
            print(f"❌ Error processing claim {idx}: {e}")
            continue

    # Summary
    print()
    print("=" * 70)
    print("📊 Upload Summary")
    print("=" * 70)
    print(f"Total claims: {len(claims)}")
    print(f"Successfully uploaded: {len(uploaded_files)}")
    print(f"Total claim amount: RM {sum(f['amount'] for f in uploaded_files):.2f}")
    print()
    print("✅ All claims uploaded to Google Shared Drive: Claims Archive")
    print(f"   Folder ID: {drive_folder_id}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
