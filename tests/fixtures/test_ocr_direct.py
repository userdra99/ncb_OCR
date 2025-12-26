#!/usr/bin/env python3
"""Direct OCR test script to test extraction from receipt image."""

import asyncio
import sys
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.services.ocr_service import OCRService
from src.utils.logging import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(__name__)


async def test_ocr_extraction():
    """Test OCR extraction on the test receipt."""
    # Path to test receipt (inside container)
    test_receipt = Path("/app/data/temp/malaysian_receipt_test.jpg")

    if not test_receipt.exists():
        logger.error(f"Test receipt not found: {test_receipt}")
        print(f"❌ Test receipt not found: {test_receipt}")
        return False

    logger.info(f"Testing OCR extraction on: {test_receipt}")
    print(f"\n🔍 Testing OCR extraction on: {test_receipt}")
    print("=" * 80)

    try:
        # Initialize OCR service
        print("📦 Initializing OCR service (CPU mode)...")
        start_init = time.time()
        ocr_service = OCRService()
        init_time = time.time() - start_init
        print(f"✅ OCR initialized in {init_time:.2f}s")

        # Extract raw text
        print("\n📝 Extracting raw text...")
        start_raw = time.time()
        ocr_result = await ocr_service.extract_text(test_receipt)
        raw_time = time.time() - start_raw

        print(f"✅ Raw extraction complete in {raw_time:.2f}s")
        print(f"   - Detected {len(ocr_result.text_blocks)} text blocks")
        print(f"   - Language: {ocr_result.detected_language}")
        print(f"   - Processing time: {ocr_result.processing_time_ms:.2f}ms")

        # Show some extracted text
        print("\n📄 Sample extracted text:")
        for i, block in enumerate(ocr_result.text_blocks[:10]):
            print(f"   {i+1}. {block['text'][:60]:<60} (conf: {block['confidence']:.3f})")
        if len(ocr_result.text_blocks) > 10:
            print(f"   ... and {len(ocr_result.text_blocks) - 10} more blocks")

        # Extract structured data
        print("\n🏥 Extracting structured claim data...")
        start_struct = time.time()
        extraction_result = await ocr_service.extract_structured_data(test_receipt)
        struct_time = time.time() - start_struct

        print(f"✅ Structured extraction complete in {struct_time:.2f}s")
        print(f"\n📊 Extraction Results:")
        print("=" * 80)
        print(f"Overall Confidence: {extraction_result.confidence_score:.2%}")
        print(f"Confidence Level:   {extraction_result.confidence_level}")

        claim = extraction_result.claim
        print(f"\n💳 Claim Data:")
        print(f"   Member ID:      {claim.member_id or 'NOT FOUND'}")
        print(f"   Member Name:    {claim.member_name or 'NOT FOUND'}")
        print(f"   Policy Number:  {claim.policy_number or 'NOT FOUND'}")
        print(f"   Provider:       {claim.provider_name or 'NOT FOUND'}")
        print(f"   Service Date:   {claim.service_date.strftime('%Y-%m-%d') if claim.service_date else 'NOT FOUND'}")
        print(f"   Total Amount:   RM {claim.total_amount:.2f}" if claim.total_amount else "   Total Amount:   NOT FOUND")
        print(f"   Receipt Number: {claim.receipt_number or 'NOT FOUND'}")
        if claim.sst_amount:
            print(f"   SST Amount:     RM {claim.sst_amount:.2f}")

        # Field confidences
        print(f"\n🎯 Field Confidence Scores:")
        for field, score in extraction_result.field_confidences.items():
            status = "✅" if score >= 0.90 else "⚠️" if score >= 0.75 else "❌"
            print(f"   {status} {field:20s} {score:.2%}")

        # Warnings
        if extraction_result.warnings:
            print(f"\n⚠️  Warnings ({len(extraction_result.warnings)}):")
            for warning in extraction_result.warnings:
                print(f"   - {warning}")

        # Performance summary
        print(f"\n⏱️  Performance Summary:")
        print(f"   OCR Initialization: {init_time:.2f}s")
        print(f"   Raw Extraction:     {raw_time:.2f}s")
        print(f"   Structured Extract: {struct_time:.2f}s")
        print(f"   Total Time:         {init_time + struct_time:.2f}s")

        # Routing decision
        print(f"\n🚦 Routing Decision:")
        if extraction_result.confidence_score >= 0.90:
            print("   ✅ HIGH CONFIDENCE - Auto-submit to NCB")
        elif extraction_result.confidence_score >= 0.75:
            print("   ⚠️  MEDIUM CONFIDENCE - Submit with manual review flag")
        else:
            print("   ❌ LOW CONFIDENCE - Route to exception queue")

        print("=" * 80)
        print("✅ OCR test completed successfully!")
        return True

    except Exception as e:
        logger.error(f"OCR test failed: {e}", exc_info=True)
        print(f"\n❌ OCR test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_ocr_extraction())
    sys.exit(0 if success else 1)
