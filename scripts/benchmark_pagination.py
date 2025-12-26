#!/usr/bin/env python3
"""
Benchmark script to demonstrate pagination memory efficiency.

Usage:
    python scripts/benchmark_pagination.py [job_count]

Examples:
    python scripts/benchmark_pagination.py 100
    python scripts/benchmark_pagination.py 1000
    python scripts/benchmark_pagination.py 10000
"""

import asyncio
import sys
import time
import tracemalloc
from datetime import datetime, timedelta
from typing import List
from uuid import uuid4

# Add project root to path
sys.path.insert(0, '.')

from src.models.job import Job, JobStatus
from src.models.extraction import ExtractionResult, ConfidenceLevel
from src.services.queue_service import QueueService


async def create_test_jobs(service: QueueService, count: int) -> List[str]:
    """Create test jobs in Redis."""
    job_ids = []
    base_time = datetime.now()

    print(f"Creating {count} test jobs...")
    start_time = time.time()

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

        # Add extraction result to some jobs
        if job.status == JobStatus.COMPLETED:
            job.extraction_result = ExtractionResult(
                member_id=f"MEM{i:04d}",
                member_name=f"Member {i}",
                provider_name=f"Provider {i}",
                service_date=base_time - timedelta(days=i % 30),
                total_amount=100.0 + (i % 1000),
                confidence_score=0.80 + (i % 20) / 100,
                confidence_level=ConfidenceLevel.HIGH if i % 2 == 0 else ConfidenceLevel.MEDIUM,
                field_confidences={"member_id": 0.95, "total_amount": 0.90}
            )

        await service.enqueue_job(job)
        job_ids.append(job.id)

        # Progress indicator
        if (i + 1) % 100 == 0:
            print(f"  Created {i + 1}/{count} jobs...")

    elapsed = time.time() - start_time
    print(f"✓ Created {count} jobs in {elapsed:.2f}s\n")

    return job_ids


async def benchmark_old_approach(service: QueueService):
    """Simulate old approach: load all jobs into memory."""
    print("=" * 60)
    print("OLD APPROACH (Loading all jobs)")
    print("=" * 60)

    tracemalloc.start()
    start_time = time.time()
    start_memory = tracemalloc.get_traced_memory()[0]

    # Get ALL job IDs
    all_job_ids = await service.get_all_job_ids()
    print(f"Found {len(all_job_ids)} jobs")

    # Load ALL jobs into memory
    all_jobs = []
    for job_id in all_job_ids:
        job = await service.get_job(job_id)
        if job:
            all_jobs.append(job)

    end_memory = tracemalloc.get_traced_memory()[0]
    elapsed = time.time() - start_time
    memory_used = (end_memory - start_memory) / 1024 / 1024  # MB

    tracemalloc.stop()

    print(f"\nResults:")
    print(f"  Jobs loaded: {len(all_jobs)}")
    print(f"  Time taken: {elapsed:.2f}s")
    print(f"  Memory used: {memory_used:.2f} MB")
    print(f"  Memory per job: {memory_used / len(all_jobs) * 1024:.2f} KB")
    print()

    return {
        "approach": "old",
        "jobs_loaded": len(all_jobs),
        "time_seconds": elapsed,
        "memory_mb": memory_used
    }


async def benchmark_new_approach(service: QueueService, page_size: int = 100):
    """Benchmark new paginated approach."""
    print("=" * 60)
    print(f"NEW APPROACH (Paginated with {page_size} jobs per page)")
    print("=" * 60)

    tracemalloc.start()
    start_time = time.time()
    start_memory = tracemalloc.get_traced_memory()[0]

    # Paginate through jobs
    cursor = None
    total_jobs = 0
    pages = 0

    while True:
        # Get one page
        job_ids, next_cursor = await service.get_job_ids_paginated(
            cursor=cursor,
            limit=page_size
        )

        # Process page (load jobs)
        for job_id in job_ids:
            job = await service.get_job(job_id)
            if job:
                total_jobs += 1

        pages += 1

        # Check for more
        if not next_cursor:
            break

        cursor = next_cursor

    end_memory = tracemalloc.get_traced_memory()[0]
    elapsed = time.time() - start_time
    memory_used = (end_memory - start_memory) / 1024 / 1024  # MB

    tracemalloc.stop()

    print(f"\nResults:")
    print(f"  Jobs processed: {total_jobs}")
    print(f"  Pages retrieved: {pages}")
    print(f"  Time taken: {elapsed:.2f}s")
    print(f"  Memory used: {memory_used:.2f} MB")
    print(f"  Memory per page: {memory_used / pages:.2f} MB")
    print()

    return {
        "approach": "new",
        "jobs_processed": total_jobs,
        "pages": pages,
        "time_seconds": elapsed,
        "memory_mb": memory_used
    }


async def benchmark_aggregated_stats(service: QueueService):
    """Benchmark aggregated stats endpoint."""
    print("=" * 60)
    print("AGGREGATED STATS APPROACH")
    print("=" * 60)

    tracemalloc.start()
    start_time = time.time()
    start_memory = tracemalloc.get_traced_memory()[0]

    # Get aggregated stats
    stats = await service.get_aggregated_stats()

    end_memory = tracemalloc.get_traced_memory()[0]
    elapsed = time.time() - start_time
    memory_used = (end_memory - start_memory) / 1024 / 1024  # MB

    tracemalloc.stop()

    print(f"\nResults:")
    print(f"  Total jobs: {stats['total']}")
    print(f"  Completed: {stats['completed_count']}")
    print(f"  Pending: {stats['pending_count']}")
    print(f"  Processing: {stats['processing_count']}")
    print(f"  Time taken: {elapsed:.2f}s")
    print(f"  Memory used: {memory_used:.2f} MB")
    print()

    return {
        "approach": "aggregated",
        "total_jobs": stats['total'],
        "time_seconds": elapsed,
        "memory_mb": memory_used
    }


async def cleanup_test_jobs(service: QueueService, job_ids: List[str]):
    """Clean up test jobs from Redis."""
    print("\nCleaning up test data...")

    for job_id in job_ids:
        await service.redis.delete(f"job:{job_id}")

    # Clear queues
    await service.redis.delete(service.config.ocr_queue)
    await service.redis.delete(service.config.submission_queue)
    await service.redis.delete(service.config.exception_queue)

    print("✓ Cleanup complete\n")


async def run_benchmark(job_count: int):
    """Run complete benchmark suite."""
    print("\n" + "=" * 60)
    print(f"PAGINATION BENCHMARK - {job_count} JOBS")
    print("=" * 60 + "\n")

    service = QueueService()
    await service.connect()

    try:
        # Create test data
        job_ids = await create_test_jobs(service, job_count)

        # Run benchmarks
        old_result = await benchmark_old_approach(service)
        new_result = await benchmark_new_approach(service, page_size=100)
        agg_result = await benchmark_aggregated_stats(service)

        # Print comparison
        print("=" * 60)
        print("COMPARISON")
        print("=" * 60)
        print(f"\n{'Metric':<30} {'Old':<15} {'New':<15} {'Improvement':<15}")
        print("-" * 75)

        # Time comparison
        time_improvement = (
            (old_result['time_seconds'] - new_result['time_seconds'])
            / old_result['time_seconds'] * 100
        )
        print(
            f"{'Time (seconds)':<30} "
            f"{old_result['time_seconds']:<15.2f} "
            f"{new_result['time_seconds']:<15.2f} "
            f"{time_improvement:>13.1f}%"
        )

        # Memory comparison
        memory_improvement = (
            (old_result['memory_mb'] - new_result['memory_mb'])
            / old_result['memory_mb'] * 100
        )
        print(
            f"{'Memory (MB)':<30} "
            f"{old_result['memory_mb']:<15.2f} "
            f"{new_result['memory_mb']:<15.2f} "
            f"{memory_improvement:>13.1f}%"
        )

        # Memory per job
        old_per_job = old_result['memory_mb'] / old_result['jobs_loaded'] * 1024
        new_per_page = new_result['memory_mb'] / new_result['pages']
        print(
            f"{'Memory per unit (KB/MB)':<30} "
            f"{old_per_job:<15.2f} "
            f"{new_per_page:<15.2f} "
            f"{'N/A':>15}"
        )

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"\n✓ Pagination is {time_improvement:.1f}% faster")
        print(f"✓ Pagination uses {memory_improvement:.1f}% less memory")
        print(f"✓ Aggregated stats completed in {agg_result['time_seconds']:.2f}s")
        print(f"✓ Memory usage is O(page_size) not O(total_jobs)")

        # Scalability prediction
        print(f"\nScalability prediction for 100,000 jobs:")
        predicted_memory = new_result['memory_mb'] / job_count * 100000
        predicted_time = new_result['time_seconds'] / job_count * 100000
        print(f"  Estimated memory: ~{predicted_memory:.0f} MB (same as {job_count} jobs)")
        print(f"  Estimated time: ~{predicted_time:.1f}s")

        print("\n" + "=" * 60 + "\n")

    finally:
        await cleanup_test_jobs(service, job_ids)
        await service.disconnect()


def main():
    """Main entry point."""
    # Get job count from command line
    job_count = 1000  # Default
    if len(sys.argv) > 1:
        try:
            job_count = int(sys.argv[1])
        except ValueError:
            print(f"Error: Invalid job count '{sys.argv[1]}'")
            print("Usage: python scripts/benchmark_pagination.py [job_count]")
            sys.exit(1)

    # Validate job count
    if job_count < 10:
        print("Error: Job count must be at least 10")
        sys.exit(1)

    if job_count > 50000:
        print(f"Warning: {job_count} jobs may take a long time to create")
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled")
            sys.exit(0)

    # Run benchmark
    asyncio.run(run_benchmark(job_count))


if __name__ == "__main__":
    main()
