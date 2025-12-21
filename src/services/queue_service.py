"""Redis queue service for job management."""

import json
from datetime import datetime
from typing import Optional

import redis.asyncio as aioredis

from src.config.settings import settings
from src.models.job import Job, JobStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)


class QueueService:
    """Redis job queue management."""

    def __init__(self) -> None:
        """Initialize Redis connection."""
        self.config = settings.redis
        self.redis: Optional[aioredis.Redis] = None
        logger.info("Queue service initialized", redis_url=self.config.url)

    async def connect(self) -> None:
        """Connect to Redis."""
        self.redis = await aioredis.from_url(self.config.url, decode_responses=True)
        logger.info("Connected to Redis")

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")

    async def enqueue_job(self, job: Job, queue_name: Optional[str] = None) -> str:
        """
        Add job to processing queue.

        Args:
            job: Job to enqueue
            queue_name: Queue name (defaults to OCR queue)

        Returns:
            Job ID
        """
        if not self.redis:
            await self.connect()

        queue = queue_name or self.config.ocr_queue

        # Store job data
        job_key = f"job:{job.id}"
        await self.redis.set(job_key, job.model_dump_json())

        # Add to queue
        await self.redis.lpush(queue, job.id)

        logger.info("Job enqueued", job_id=job.id, queue=queue, status=job.status)
        return job.id

    async def dequeue_job(self, queue_name: str, timeout: int = 1) -> Optional[Job]:
        """
        Get next job from queue (blocking).

        Args:
            queue_name: Queue to read from
            timeout: Block timeout in seconds

        Returns:
            Job or None if timeout
        """
        if not self.redis:
            await self.connect()

        # Blocking pop from queue
        result = await self.redis.brpop(queue_name, timeout=timeout)

        if result:
            _, job_id = result
            return await self.get_job(job_id)

        return None

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        if not self.redis:
            await self.connect()

        job_key = f"job:{job_id}"
        job_data = await self.redis.get(job_key)

        if job_data:
            return Job.model_validate_json(job_data)

        return None

    async def update_job_status(
        self, job_id: str, status: JobStatus, **kwargs
    ) -> None:
        """
        Update job status and optional fields.

        Args:
            job_id: Job ID
            status: New status
            **kwargs: Additional fields to update
        """
        if not self.redis:
            await self.connect()

        job = await self.get_job(job_id)
        if not job:
            logger.warning("Job not found for update", job_id=job_id)
            return

        # Update status and timestamp
        job.status = status
        job.updated_at = datetime.now()

        # Update additional fields
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)

        # Save updated job
        job_key = f"job:{job_id}"
        await self.redis.set(job_key, job.model_dump_json())

        logger.info("Job status updated", job_id=job_id, status=status)

        # If status is exception, add to exception queue
        if status == JobStatus.EXCEPTION:
            await self.redis.lpush(self.config.exception_queue, job_id)

    async def get_pending_jobs(self, queue_name: Optional[str] = None) -> list[Job]:
        """Get all pending jobs."""
        if not self.redis:
            await self.connect()

        queue = queue_name or self.config.ocr_queue
        job_ids = await self.redis.lrange(queue, 0, -1)

        jobs = []
        for job_id in job_ids:
            job = await self.get_job(job_id)
            if job:
                jobs.append(job)

        return jobs

    async def get_exception_queue(self) -> list[Job]:
        """Get jobs in exception status."""
        if not self.redis:
            await self.connect()

        job_ids = await self.redis.lrange(self.config.exception_queue, 0, -1)

        jobs = []
        for job_id in job_ids:
            job = await self.get_job(job_id)
            if job and job.status == JobStatus.EXCEPTION:
                jobs.append(job)

        return jobs

    async def check_duplicate(self, file_hash: str) -> bool:
        """Check if attachment already processed."""
        if not self.redis:
            await self.connect()

        hash_key = f"hash:{file_hash}"
        return await self.redis.exists(hash_key) > 0

    async def record_hash(self, file_hash: str, job_id: str, ttl: int = 2592000) -> None:
        """
        Record file hash for deduplication.

        Args:
            file_hash: File hash
            job_id: Associated job ID
            ttl: Time to live in seconds (default 30 days)
        """
        if not self.redis:
            await self.connect()

        hash_key = f"hash:{file_hash}"
        await self.redis.setex(hash_key, ttl, job_id)

        logger.debug("File hash recorded", file_hash=file_hash, job_id=job_id)

    async def get_queue_size(self, queue_name: str) -> int:
        """Get number of jobs in queue."""
        if not self.redis:
            await self.connect()

        return await self.redis.llen(queue_name)
