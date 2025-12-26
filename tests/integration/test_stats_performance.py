"""Integration tests for stats API performance with large datasets."""

import asyncio
import pytest
import time
import tracemalloc
from datetime import datetime, timedelta
from typing import List
from uuid import uuid4

from src.models.job import Job, JobStatus
from src.models.extraction import ExtractionResult, ConfidenceLevel
from src.services.queue_service import QueueService


@pytest.fixture
async def queue_service_with_redis():
    """Create QueueService with real Redis connection."""
    service = QueueService()
    await service.connect()
    yield service
    await service.disconnect()


async def create_test_jobs(service: QueueService, count: int) -> List[str]:
    """
    Create test jobs in Redis for performance testing.

    Args:
        service: QueueService instance
        count: Number of jobs to create

    Returns:
        List of created job IDs
    """
    job_ids = []
    base_time = datetime.now()

    for i in range(count):
        job = Job(
            id=str(uuid4()),
            email_id=f"test_{i}@example.com",
            attachment_filename=f"receipt_{i}.jpg",
            attachment_path=f"/tmp/receipt_{i}.jpg",
            attachment_hash=f"hash_{i}",
            status=JobStatus.COMPLETED if i % 3 == 0 else (
                JobStatus.PENDING if i % 3 == 1 else JobStatus.PROCESSING
            ),
            created_at=base_time - timedelta(hours=i % 100),
            updated_at=base_time - timedelta(hours=i % 100) + timedelta(minutes=5),
            retry_count=0
        )

        # Add extraction result to completed jobs
        if job.status == JobStatus.COMPLETED:
            job.extraction_result = ExtractionResult(
                member_id=f"MEM{i:04d}",
                member_name=f"Member {i}",
                provider_name=f"Provider {i}",
                service_date=base_time - timedelta(days=i % 30),
                total_amount=100.0 + (i % 1000),
                confidence_score=0.80 + (i % 20) / 100,
                confidence_level=ConfidenceLevel.HIGH if i % 2 == 0 else ConfidenceLevel.MEDIUM,
                field_confidences={
                    "member_id": 0.95,
                    "total_amount": 0.90
                }
            )
            job.ncb_reference = f"NCB-{i:06d}"

        await service.enqueue_job(job)
        job_ids.append(job.id)

    return job_ids


async def cleanup_test_jobs(service: QueueService, job_ids: List[str]):
    """Clean up test jobs from Redis."""
    if not service.redis:
        return

    # Delete job data
    for job_id in job_ids:
        await service.redis.delete(f"job:{job_id}")

    # Clear queues
    await service.redis.delete(service.config.ocr_queue)
    await service.redis.delete(service.config.submission_queue)
    await service.redis.delete(service.config.exception_queue)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pagination_performance_100_jobs(queue_service_with_redis):
    """Test pagination performance with 100 jobs."""
    service = queue_service_with_redis
    job_count = 100

    try:
        # Create test data
        print(f"\nCreating {job_count} test jobs...")
        job_ids = await create_test_jobs(service, job_count)

        # Test pagination
        print("Testing pagination...")
        start_time = time.time()

        # Get first page
        page_job_ids, next_cursor = await service.get_job_ids_paginated(
            cursor=None,
            limit=50
        )

        elapsed = time.time() - start_time

        # Assertions
        assert len(page_job_ids) == 50
        assert next_cursor is not None
        assert elapsed < 1.0, f"Pagination too slow: {elapsed:.2f}s"

        print(f"✓ Retrieved 50 jobs in {elapsed*1000:.2f}ms")

        # Get second page
        start_time = time.time()
        page_job_ids, next_cursor = await service.get_job_ids_paginated(
            cursor=next_cursor,
            limit=50
        )
        elapsed = time.time() - start_time

        assert len(page_job_ids) <= 50
        assert elapsed < 1.0, f"Pagination too slow: {elapsed:.2f}s"

        print(f"✓ Retrieved next page in {elapsed*1000:.2f}ms")

    finally:
        await cleanup_test_jobs(service, job_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pagination_performance_1000_jobs(queue_service_with_redis):
    """Test pagination performance with 1,000 jobs."""
    service = queue_service_with_redis
    job_count = 1000

    try:
        # Create test data
        print(f"\nCreating {job_count} test jobs...")
        creation_start = time.time()
        job_ids = await create_test_jobs(service, job_count)
        creation_time = time.time() - creation_start
        print(f"Created {job_count} jobs in {creation_time:.2f}s")

        # Test pagination with memory tracking
        tracemalloc.start()
        start_time = time.time()
        start_memory = tracemalloc.get_traced_memory()[0]

        # Get first page
        page_job_ids, next_cursor = await service.get_job_ids_paginated(
            cursor=None,
            limit=100
        )

        end_memory = tracemalloc.get_traced_memory()[0]
        elapsed = time.time() - start_time
        memory_used = (end_memory - start_memory) / 1024 / 1024  # MB

        tracemalloc.stop()

        # Assertions
        assert len(page_job_ids) == 100
        assert next_cursor is not None
        assert elapsed < 0.5, f"Pagination too slow: {elapsed:.2f}s"
        assert memory_used < 10, f"Too much memory used: {memory_used:.2f}MB"

        print(f"✓ Retrieved 100 jobs from 1000 in {elapsed*1000:.2f}ms")
        print(f"✓ Memory used: {memory_used:.2f}MB")

        # Paginate through all jobs
        cursor = next_cursor
        pages_retrieved = 1

        while cursor:
            page_job_ids, cursor = await service.get_job_ids_paginated(
                cursor=cursor,
                limit=100
            )
            pages_retrieved += 1

        print(f"✓ Retrieved all jobs in {pages_retrieved} pages")

    finally:
        await cleanup_test_jobs(service, job_ids)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.slow
async def test_pagination_performance_10000_jobs(queue_service_with_redis):
    """Test pagination performance with 10,000 jobs (slow test)."""
    service = queue_service_with_redis
    job_count = 10000

    try:
        # Create test data
        print(f"\nCreating {job_count} test jobs (this may take a while)...")
        creation_start = time.time()
        job_ids = await create_test_jobs(service, job_count)
        creation_time = time.time() - creation_start
        print(f"Created {job_count} jobs in {creation_time:.2f}s")

        # Test pagination with memory tracking
        tracemalloc.start()
        start_time = time.time()
        start_memory = tracemalloc.get_traced_memory()[0]

        # Get first page
        page_job_ids, next_cursor = await service.get_job_ids_paginated(
            cursor=None,
            limit=100
        )

        end_memory = tracemalloc.get_traced_memory()[0]
        elapsed = time.time() - start_time
        memory_used = (end_memory - start_memory) / 1024 / 1024  # MB

        tracemalloc.stop()

        # Assertions - should be fast even with 10k jobs
        assert len(page_job_ids) == 100
        assert next_cursor is not None
        assert elapsed < 1.0, f"Pagination too slow: {elapsed:.2f}s"
        assert memory_used < 20, f"Too much memory used: {memory_used:.2f}MB"

        print(f"✓ Retrieved 100 jobs from 10,000 in {elapsed*1000:.2f}ms")
        print(f"✓ Memory used: {memory_used:.2f}MB (demonstrates O(limit) not O(n))")

    finally:
        await cleanup_test_jobs(service, job_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_aggregated_stats_performance(queue_service_with_redis):
    """Test aggregated stats performance with large dataset."""
    service = queue_service_with_redis
    job_count = 1000

    try:
        # Create test data
        print(f"\nCreating {job_count} test jobs...")
        job_ids = await create_test_jobs(service, job_count)

        # Test aggregated stats
        print("Testing aggregated stats...")
        start_time = time.time()

        stats = await service.get_aggregated_stats()

        elapsed = time.time() - start_time

        # Assertions
        assert stats["total"] > 0
        assert stats["total"] <= job_count
        assert "completed_count" in stats
        assert "pending_count" in stats
        assert "queue_sizes" in stats
        assert elapsed < 5.0, f"Aggregation too slow: {elapsed:.2f}s"

        print(f"✓ Aggregated {stats['total']} jobs in {elapsed:.2f}s")
        print(f"  - Completed: {stats['completed_count']}")
        print(f"  - Pending: {stats['pending_count']}")
        print(f"  - Processing: {stats['processing_count']}")

    finally:
        await cleanup_test_jobs(service, job_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_status_filter_performance(queue_service_with_redis):
    """Test pagination with status filtering."""
    service = queue_service_with_redis
    job_count = 500

    try:
        # Create test data
        print(f"\nCreating {job_count} test jobs...")
        job_ids = await create_test_jobs(service, job_count)

        # Test filtering by status
        print("Testing status filtering...")
        start_time = time.time()

        page_job_ids, next_cursor = await service.get_job_ids_paginated(
            cursor=None,
            limit=50,
            status=JobStatus.COMPLETED
        )

        elapsed = time.time() - start_time

        # Verify all returned jobs are completed
        for job_id in page_job_ids:
            job = await service.get_job(job_id)
            assert job.status == JobStatus.COMPLETED

        assert len(page_job_ids) > 0
        assert elapsed < 2.0, f"Filtered pagination too slow: {elapsed:.2f}s"

        print(f"✓ Filtered {len(page_job_ids)} completed jobs in {elapsed*1000:.2f}ms")

    finally:
        await cleanup_test_jobs(service, job_ids)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_pagination(queue_service_with_redis):
    """Test concurrent pagination requests."""
    service = queue_service_with_redis
    job_count = 500

    try:
        # Create test data
        print(f"\nCreating {job_count} test jobs...")
        job_ids = await create_test_jobs(service, job_count)

        # Test concurrent pagination
        print("Testing concurrent pagination...")

        async def paginate_concurrently():
            results = await asyncio.gather(
                service.get_job_ids_paginated(cursor=None, limit=50),
                service.get_job_ids_paginated(cursor=None, limit=100),
                service.get_job_ids_paginated(cursor=None, limit=25),
            )
            return results

        start_time = time.time()
        results = await paginate_concurrently()
        elapsed = time.time() - start_time

        # Verify results
        assert len(results) == 3
        assert len(results[0][0]) <= 50
        assert len(results[1][0]) <= 100
        assert len(results[2][0]) <= 25
        assert elapsed < 2.0, f"Concurrent pagination too slow: {elapsed:.2f}s"

        print(f"✓ Handled 3 concurrent requests in {elapsed*1000:.2f}ms")

    finally:
        await cleanup_test_jobs(service, job_ids)


if __name__ == "__main__":
    """Run performance tests directly."""
    import sys

    async def run_tests():
        """Run all performance tests."""
        service = QueueService()
        await service.connect()

        try:
            print("=" * 60)
            print("STATS API PERFORMANCE TESTS")
            print("=" * 60)

            await test_pagination_performance_100_jobs(service)
            await test_pagination_performance_1000_jobs(service)
            await test_aggregated_stats_performance(service)
            await test_status_filter_performance(service)
            await test_concurrent_pagination(service)

            print("\n" + "=" * 60)
            print("ALL TESTS PASSED ✓")
            print("=" * 60)

        finally:
            await service.disconnect()

    # Run tests
    asyncio.run(run_tests())
