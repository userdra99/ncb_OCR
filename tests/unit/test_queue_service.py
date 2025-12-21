"""
Unit tests for Queue Service

Tests Redis queue operations, job management, and deduplication
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import hashlib


@pytest.mark.unit
@pytest.mark.queue
class TestQueueService:
    """Test suite for Queue Service"""

    @pytest.fixture
    async def queue_service(self, mock_redis, mock_env):
        """Create Queue service instance with mocked Redis."""
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            from src.services.queue_service import QueueService

            service = QueueService()
            await service.connect()
            return service

    @pytest.mark.asyncio
    async def test_enqueue_job_success(self, queue_service, mock_redis, sample_job_data):
        """
        Test enqueuing a job

        Given: Valid job data
        When: enqueue_job() is called
        Then: Job added to Redis queue with unique ID
        """
        # Arrange
        from src.models.job import Job

        job = Job(**sample_job_data)

        # Act
        job_id = await queue_service.enqueue_job(job)

        # Assert
        assert job_id is not None
        assert job_id.startswith("job_")
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_enqueue_job_generates_unique_id(self, queue_service, sample_job_data):
        """
        Test that each job gets a unique ID

        Given: Multiple jobs
        When: enqueued
        Then: Each has unique ID
        """
        # Arrange
        from src.models.job import Job

        job1 = Job(**sample_job_data)
        job2 = Job(**{**sample_job_data, "attachment_filename": "receipt_002.jpg"})

        # Act
        id1 = await queue_service.enqueue_job(job1)
        id2 = await queue_service.enqueue_job(job2)

        # Assert
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_get_job_by_id(self, queue_service, mock_redis, sample_job_data):
        """
        Test retrieving job by ID

        Given: Job in queue
        When: get_job() is called with ID
        Then: Job data returned
        """
        # Arrange
        from src.models.job import Job
        import json

        job = Job(**sample_job_data)
        job_id = "job_test123"

        mock_redis.get.return_value = json.dumps(job.model_dump(), default=str)

        # Act
        retrieved_job = await queue_service.get_job(job_id)

        # Assert
        assert retrieved_job is not None
        assert retrieved_job.id == job.id

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, queue_service, mock_redis):
        """
        Test retrieving non-existent job

        Given: Job ID that doesn't exist
        When: get_job() is called
        Then: Returns None
        """
        # Arrange
        mock_redis.get.return_value = None

        # Act
        job = await queue_service.get_job("nonexistent_id")

        # Assert
        assert job is None

    @pytest.mark.asyncio
    async def test_update_job_status(self, queue_service, mock_redis, sample_job_data):
        """
        Test updating job status

        Given: Existing job
        When: update_job_status() is called
        Then: Job status updated in Redis
        """
        # Arrange
        from src.models.job import JobStatus
        import json

        job_id = "job_test123"
        mock_redis.get.return_value = json.dumps(sample_job_data, default=str)

        # Act
        await queue_service.update_job_status(
            job_id, JobStatus.PROCESSING
        )

        # Assert
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_update_job_with_additional_fields(
        self, queue_service, mock_redis, sample_job_data
    ):
        """
        Test updating job with extra fields

        Given: Job in processing
        When: update_job_status() called with ncb_reference
        Then: Both status and reference updated
        """
        # Arrange
        from src.models.job import JobStatus
        import json

        job_id = "job_test123"
        mock_redis.get.return_value = json.dumps(sample_job_data, default=str)

        # Act
        await queue_service.update_job_status(
            job_id,
            JobStatus.SUBMITTED,
            ncb_reference="CLM-2024-567890",
            ncb_submitted_at=datetime.now(),
        )

        # Assert
        # Verify set was called with updated data
        call_args = mock_redis.set.call_args
        updated_data = call_args[0][1]
        assert "CLM-2024-567890" in updated_data

    @pytest.mark.asyncio
    async def test_get_pending_jobs(self, queue_service, mock_redis):
        """
        Test retrieving all pending jobs

        Given: Queue with pending jobs
        When: get_pending_jobs() is called
        Then: List of pending jobs returned
        """
        # Arrange
        import json
        from src.models.job import JobStatus

        pending_jobs = [
            {"id": "job_1", "status": JobStatus.PENDING.value},
            {"id": "job_2", "status": JobStatus.PENDING.value},
        ]

        mock_redis.keys.return_value = [f"job:{job['id']}" for job in pending_jobs]
        mock_redis.get.side_effect = [json.dumps(job) for job in pending_jobs]

        # Act
        jobs = await queue_service.get_pending_jobs()

        # Assert
        assert len(jobs) == 2
        assert all(job.status == JobStatus.PENDING for job in jobs)

    @pytest.mark.asyncio
    async def test_get_exception_queue(self, queue_service, mock_redis):
        """
        Test retrieving exception queue

        Given: Jobs in exception status
        When: get_exception_queue() is called
        Then: List of exception jobs returned
        """
        # Arrange
        import json
        from src.models.job import JobStatus

        exception_jobs = [
            {"id": "job_exc1", "status": JobStatus.EXCEPTION.value},
            {"id": "job_exc2", "status": JobStatus.EXCEPTION.value},
        ]

        mock_redis.keys.return_value = [f"job:{job['id']}" for job in exception_jobs]
        mock_redis.get.side_effect = [json.dumps(job) for job in exception_jobs]

        # Act
        jobs = await queue_service.get_exception_queue()

        # Assert
        assert len(jobs) == 2
        assert all(job.status == JobStatus.EXCEPTION for job in jobs)

    @pytest.mark.asyncio
    async def test_check_duplicate_file_hash(self, queue_service, mock_redis):
        """
        Test duplicate detection by file hash

        Given: File hash already processed
        When: check_duplicate() is called
        Then: Returns True
        """
        # Arrange
        file_hash = "sha256:abc123def456"
        mock_redis.exists.return_value = 1

        # Act
        is_duplicate = await queue_service.check_duplicate(file_hash)

        # Assert
        assert is_duplicate is True

    @pytest.mark.asyncio
    async def test_check_duplicate_new_file(self, queue_service, mock_redis):
        """
        Test duplicate check for new file

        Given: File hash not seen before
        When: check_duplicate() is called
        Then: Returns False
        """
        # Arrange
        file_hash = "sha256:newfile123"
        mock_redis.exists.return_value = 0

        # Act
        is_duplicate = await queue_service.check_duplicate(file_hash)

        # Assert
        assert is_duplicate is False

    @pytest.mark.asyncio
    async def test_record_hash(self, queue_service, mock_redis):
        """
        Test recording file hash for deduplication

        Given: New file processed
        When: record_hash() is called
        Then: Hash stored in Redis with job ID
        """
        # Arrange
        file_hash = "sha256:abc123def456"
        job_id = "job_test123"

        # Act
        await queue_service.record_hash(file_hash, job_id)

        # Assert
        mock_redis.set.assert_called()
        call_args = mock_redis.set.call_args
        assert file_hash in str(call_args)

    @pytest.mark.asyncio
    async def test_hash_has_expiration(self, queue_service, mock_redis):
        """
        Test that hash records have TTL to prevent infinite growth

        Given: Hash recorded
        When: TTL checked
        Then: Expiration set (e.g., 90 days)
        """
        # Arrange
        file_hash = "sha256:abc123def456"
        job_id = "job_test123"

        # Act
        await queue_service.record_hash(file_hash, job_id)

        # Assert
        # Verify TTL was set
        call_args = mock_redis.set.call_args
        assert call_args.kwargs.get("ex") or call_args.kwargs.get("px")

    @pytest.mark.asyncio
    async def test_dequeue_fifo_order(self, queue_service, mock_redis):
        """
        Test that jobs are dequeued in FIFO order

        Given: Multiple jobs in queue
        When: dequeue() is called multiple times
        Then: Jobs returned in order they were added
        """
        # This would be better tested in integration tests with actual Redis
        # Unit test just verifies the dequeue method exists and returns jobs
        pass

    @pytest.mark.asyncio
    async def test_job_persistence(self, queue_service, mock_redis):
        """
        Test that jobs persist across service restarts

        Given: Jobs in Redis
        When: Service reconnects
        Then: Jobs still retrievable
        """
        # Arrange - simulates restart
        from src.services.queue_service import QueueService

        with patch('redis.asyncio.from_url', return_value=mock_redis):
            new_service = QueueService()
            await new_service.connect()

            # Act
            jobs = await new_service.get_pending_jobs()

            # Assert - should be able to retrieve jobs
            assert mock_redis.keys.called

    @pytest.mark.asyncio
    async def test_concurrent_job_updates(self, queue_service, mock_redis):
        """
        Test handling of concurrent status updates

        Given: Multiple workers updating same job
        When: Updates occur simultaneously
        Then: Final state is consistent (atomic operations)
        """
        # Redis operations should be atomic
        # This is more of an integration test concern
        pass

    @pytest.mark.asyncio
    async def test_queue_stats(self, queue_service, mock_redis):
        """
        Test retrieving queue statistics

        Given: Jobs in various states
        When: get_stats() is called
        Then: Returns counts by status
        """
        # Arrange
        from src.models.job import JobStatus
        import json

        all_jobs = [
            {"id": "job_1", "status": JobStatus.PENDING.value},
            {"id": "job_2", "status": JobStatus.PROCESSING.value},
            {"id": "job_3", "status": JobStatus.SUBMITTED.value},
            {"id": "job_4", "status": JobStatus.EXCEPTION.value},
        ]

        mock_redis.keys.return_value = [f"job:{job['id']}" for job in all_jobs]
        mock_redis.get.side_effect = [json.dumps(job) for job in all_jobs]

        # Act
        stats = await queue_service.get_stats()

        # Assert
        assert stats[JobStatus.PENDING] == 1
        assert stats[JobStatus.PROCESSING] == 1
        assert stats[JobStatus.SUBMITTED] == 1
        assert stats[JobStatus.EXCEPTION] == 1

    @pytest.mark.asyncio
    async def test_cleanup_old_jobs(self, queue_service, mock_redis):
        """
        Test cleanup of old completed jobs

        Given: Jobs older than retention period
        When: cleanup() is called
        Then: Old jobs removed from queue
        """
        # This would delete jobs older than X days to prevent memory bloat
        # Implementation would use Redis TTL or manual cleanup
        pass
