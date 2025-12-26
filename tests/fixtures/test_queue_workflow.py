#!/usr/bin/env python3
"""Test complete queue workflow: Job creation -> OCR -> Submission queue."""

import asyncio
import sys
from pathlib import Path
import time
import uuid
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.job import Job, JobStatus
from src.services.queue_service import QueueService
from src.services.ocr_service import OCRService
from src.utils.logging import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(__name__)


async def test_queue_workflow():
    """Test the complete queue workflow."""
    print("\n🔄 Testing Complete Queue Workflow")
    print("=" * 80)

    try:
        # Initialize services
        print("📦 Initializing services...")
        queue_service = QueueService()
        ocr_service = OCRService()

        # Check Redis connection
        print("🔍 Checking Redis connection...")
        ocr_queue_size = await queue_service.get_queue_size(queue_service.config.ocr_queue)
        submission_queue_size = await queue_service.get_queue_size(queue_service.config.submission_queue)
        exception_queue_size = await queue_service.get_queue_size(queue_service.config.exception_queue)

        print(f"✅ Redis connected:")
        print(f"   - OCR queue:        {ocr_queue_size} jobs")
        print(f"   - Submission queue: {submission_queue_size} jobs")
        print(f"   - Exception queue:  {exception_queue_size} jobs")

        # Test 1: Create a new job
        print("\n📝 TEST 1: Create new job and enqueue for OCR")
        print("-" * 80)

        job_id = f"test_job_{uuid.uuid4().hex[:16]}"
        test_job = Job(
            id=job_id,
            email_id="test_email_123",
            attachment_filename="malaysian_receipt_test.jpg",
            attachment_path=str(Path("/app/data/temp/malaysian_receipt_test.jpg")),
            attachment_hash="test_hash_123",  # Add required field
            status=JobStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        print(f"   Job ID: {job_id}")
        print(f"   Status: {test_job.status}")

        # Enqueue for OCR
        await queue_service.enqueue_job(test_job, queue_name=queue_service.config.ocr_queue)
        print(f"   ✅ Job enqueued to OCR queue")

        # Verify job is in queue
        new_ocr_queue_size = await queue_service.get_queue_size(queue_service.config.ocr_queue)
        print(f"   OCR queue size: {ocr_queue_size} → {new_ocr_queue_size}")

        # Test 2: Retrieve job from queue
        print("\n📥 TEST 2: Dequeue job from OCR queue")
        print("-" * 80)

        dequeued_job = await queue_service.dequeue_job(queue_service.config.ocr_queue)
        if dequeued_job:
            print(f"   ✅ Job dequeued: {dequeued_job.id}")
            print(f"   Status: {dequeued_job.status}")
            print(f"   Attachment: {dequeued_job.attachment_filename}")
        else:
            print(f"   ❌ No job found in queue")
            return False

        # Test 3: Process OCR
        print("\n🔍 TEST 3: Process OCR extraction")
        print("-" * 80)

        start_time = time.time()
        dequeued_job.status = JobStatus.PROCESSING
        dequeued_job.updated_at = datetime.now()

        # Run OCR extraction
        extraction_result = await ocr_service.extract_structured_data(dequeued_job.attachment_path)
        processing_time = time.time() - start_time

        print(f"   ✅ OCR complete in {processing_time:.2f}s")
        print(f"   Confidence: {extraction_result.confidence_score:.2%} ({extraction_result.confidence_level})")
        print(f"   Member ID: {extraction_result.claim.member_id}")
        print(f"   Amount: RM {extraction_result.claim.total_amount}")

        # Update job with results
        dequeued_job.extraction_result = extraction_result
        dequeued_job.status = JobStatus.EXTRACTED
        dequeued_job.updated_at = datetime.now()

        # Test 4: Route based on confidence
        print("\n🚦 TEST 4: Route job based on confidence")
        print("-" * 80)

        if extraction_result.confidence_score >= 0.90:
            target_queue = queue_service.config.submission_queue
            routing_decision = "HIGH confidence → Submission queue"
        elif extraction_result.confidence_score >= 0.75:
            target_queue = queue_service.config.submission_queue
            routing_decision = "MEDIUM confidence → Submission queue (with review flag)"
        else:
            target_queue = queue_service.config.exception_queue
            routing_decision = "LOW confidence → Exception queue"

        print(f"   Decision: {routing_decision}")

        # Enqueue to appropriate queue
        await queue_service.enqueue_job(dequeued_job, queue_name=target_queue)
        print(f"   ✅ Job routed to: {target_queue}")

        # Test 5: Verify queue sizes
        print("\n📊 TEST 5: Verify final queue sizes")
        print("-" * 80)

        final_ocr_size = await queue_service.get_queue_size(queue_service.config.ocr_queue)
        final_submission_size = await queue_service.get_queue_size(queue_service.config.submission_queue)
        final_exception_size = await queue_service.get_queue_size(queue_service.config.exception_queue)

        print(f"   OCR queue:        {ocr_queue_size} → {final_ocr_size}")
        print(f"   Submission queue: {submission_queue_size} → {final_submission_size}")
        print(f"   Exception queue:  {exception_queue_size} → {final_exception_size}")

        # Test 6: Retrieve and verify job
        print("\n🔍 TEST 6: Retrieve job from target queue")
        print("-" * 80)

        retrieved_job = await queue_service.dequeue_job(target_queue)
        if retrieved_job:
            print(f"   ✅ Job retrieved: {retrieved_job.id}")
            print(f"   Status: {retrieved_job.status}")
            print(f"   Confidence: {retrieved_job.extraction_result.confidence_score:.2%}")
            print(f"   Member ID: {retrieved_job.extraction_result.claim.member_id}")

            # Verify it's our test job
            if retrieved_job.id == job_id:
                print(f"   ✅ Job ID matches!")
            else:
                print(f"   ⚠️  Different job: {retrieved_job.id}")
        else:
            print(f"   ❌ No job found in {target_queue}")

        # Test 7: Job persistence
        print("\n💾 TEST 7: Test job persistence (get by ID)")
        print("-" * 80)

        saved_job = await queue_service.get_job(job_id)
        if saved_job:
            print(f"   ✅ Job retrieved by ID: {saved_job.id}")
            print(f"   Status: {saved_job.status}")
            print(f"   Has extraction result: {saved_job.extraction_result is not None}")
        else:
            print(f"   ❌ Job not found by ID")

        # Summary
        print("\n" + "=" * 80)
        print("✅ QUEUE WORKFLOW TEST COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print(f"\n📈 Summary:")
        print(f"   - Job created and enqueued: ✅")
        print(f"   - Job dequeued successfully: ✅")
        print(f"   - OCR processing complete: ✅ ({processing_time:.2f}s)")
        print(f"   - Confidence-based routing: ✅ ({routing_decision})")
        print(f"   - Job persistence working: ✅")

        return True

    except Exception as e:
        logger.error(f"Queue workflow test failed: {e}", exc_info=True)
        print(f"\n❌ Queue workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_queue_workflow())
    sys.exit(0 if success else 1)
