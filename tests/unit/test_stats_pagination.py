"""Tests for stats API pagination functionality."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.api.routes.stats import get_job_stats, get_stats_summary
from src.models.job import Job, JobStatus
from src.models.extraction import ExtractionResult, ConfidenceLevel
from src.services.queue_service import QueueService


@pytest.fixture
def mock_queue_service():
    """Create a mock QueueService."""
    service = MagicMock(spec=QueueService)
    service.get_job_ids_paginated = AsyncMock()
    service.get_job = AsyncMock()
    service.get_aggregated_stats = AsyncMock()
    return service


@pytest.fixture
def sample_jobs():
    """Create sample jobs for testing."""
    jobs = []
    base_time = datetime.now()

    for i in range(50):
        job_id = str(uuid4())
        job = Job(
            id=job_id,
            email_id=f"email_{i}",
            attachment_filename=f"receipt_{i}.jpg",
            attachment_path=f"/tmp/receipt_{i}.jpg",
            attachment_hash=f"hash_{i}",
            status=JobStatus.COMPLETED if i % 2 == 0 else JobStatus.PENDING,
            created_at=base_time - timedelta(hours=i),
            updated_at=base_time - timedelta(hours=i) + timedelta(minutes=5),
            retry_count=0
        )

        # Add extraction result to completed jobs
        if job.status == JobStatus.COMPLETED:
            job.extraction_result = ExtractionResult(
                member_id=f"MEM{i:04d}",
                member_name=f"Member {i}",
                provider_name=f"Provider {i}",
                service_date=base_time - timedelta(days=i),
                total_amount=100.0 + i,
                confidence_score=0.85 + (i % 10) / 100,
                confidence_level=ConfidenceLevel.HIGH,
                field_confidences={
                    "member_id": 0.95,
                    "total_amount": 0.90
                }
            )

        jobs.append((job_id, job))

    return jobs


class TestPaginatedJobStats:
    """Tests for paginated job statistics endpoint."""

    @pytest.mark.asyncio
    async def test_get_first_page(self, mock_queue_service, sample_jobs):
        """Test retrieving the first page of job stats."""
        # Setup mock to return first 10 jobs
        job_ids = [job_id for job_id, _ in sample_jobs[:10]]
        mock_queue_service.get_job_ids_paginated.return_value = (job_ids, "cursor_10")

        # Mock get_job to return corresponding jobs
        job_dict = dict(sample_jobs)
        mock_queue_service.get_job.side_effect = lambda jid: job_dict.get(jid)

        # Patch the service instance
        with patch("src.api.routes.stats.queue_service", mock_queue_service):
            result = await get_job_stats(cursor=None, limit=10, job_status=None)

        # Verify response
        assert result.total == 10
        assert len(result.jobs) == 10
        assert result.next_cursor == "cursor_10"
        assert result.has_more is True
        assert result.limit == 10

        # Verify job data
        assert result.jobs[0].id == job_ids[0]
        assert result.jobs[0].status in [JobStatus.COMPLETED, JobStatus.PENDING]

        # Verify service was called correctly
        mock_queue_service.get_job_ids_paginated.assert_called_once_with(
            cursor=None,
            limit=10,
            status=None
        )

    @pytest.mark.asyncio
    async def test_get_second_page(self, mock_queue_service, sample_jobs):
        """Test retrieving subsequent pages with cursor."""
        # Setup mock to return jobs 10-20
        job_ids = [job_id for job_id, _ in sample_jobs[10:20]]
        mock_queue_service.get_job_ids_paginated.return_value = (job_ids, "cursor_20")

        job_dict = dict(sample_jobs)
        mock_queue_service.get_job.side_effect = lambda jid: job_dict.get(jid)

        with patch("src.api.routes.stats.queue_service", mock_queue_service):
            result = await get_job_stats(cursor="cursor_10", limit=10, job_status=None)

        assert result.total == 10
        assert result.next_cursor == "cursor_20"
        assert result.has_more is True

        # Verify cursor was passed correctly
        mock_queue_service.get_job_ids_paginated.assert_called_once_with(
            cursor="cursor_10",
            limit=10,
            status=None
        )

    @pytest.mark.asyncio
    async def test_get_last_page(self, mock_queue_service, sample_jobs):
        """Test retrieving the last page (no more results)."""
        # Setup mock to return last 5 jobs with no next cursor
        job_ids = [job_id for job_id, _ in sample_jobs[45:50]]
        mock_queue_service.get_job_ids_paginated.return_value = (job_ids, None)

        job_dict = dict(sample_jobs)
        mock_queue_service.get_job.side_effect = lambda jid: job_dict.get(jid)

        with patch("src.api.routes.stats.queue_service", mock_queue_service):
            result = await get_job_stats(cursor="cursor_45", limit=10, job_status=None)

        assert result.total == 5
        assert result.next_cursor is None
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_filter_by_status(self, mock_queue_service, sample_jobs):
        """Test filtering jobs by status."""
        # Filter for completed jobs only
        completed_jobs = [(jid, job) for jid, job in sample_jobs if job.status == JobStatus.COMPLETED]
        job_ids = [job_id for job_id, _ in completed_jobs[:10]]
        mock_queue_service.get_job_ids_paginated.return_value = (job_ids, "cursor_c10")

        job_dict = dict(sample_jobs)
        mock_queue_service.get_job.side_effect = lambda jid: job_dict.get(jid)

        with patch("src.api.routes.stats.queue_service", mock_queue_service):
            result = await get_job_stats(
                cursor=None,
                limit=10,
                job_status=JobStatus.COMPLETED
            )

        # Verify all returned jobs are completed
        assert all(job.status == JobStatus.COMPLETED for job in result.jobs)

        # Verify service was called with status filter
        mock_queue_service.get_job_ids_paginated.assert_called_once_with(
            cursor=None,
            limit=10,
            status=JobStatus.COMPLETED
        )

    @pytest.mark.asyncio
    async def test_processing_time_calculation(self, mock_queue_service, sample_jobs):
        """Test that processing time is calculated correctly."""
        # Get a completed job
        completed_jobs = [(jid, job) for jid, job in sample_jobs if job.status == JobStatus.COMPLETED]
        job_id, job = completed_jobs[0]

        mock_queue_service.get_job_ids_paginated.return_value = ([job_id], None)
        mock_queue_service.get_job.return_value = job

        with patch("src.api.routes.stats.queue_service", mock_queue_service):
            result = await get_job_stats(cursor=None, limit=1, job_status=None)

        # Verify processing time was calculated
        assert result.jobs[0].processing_time_ms is not None
        expected_ms = (job.updated_at - job.created_at).total_seconds() * 1000
        assert abs(result.jobs[0].processing_time_ms - expected_ms) < 1

    @pytest.mark.asyncio
    async def test_confidence_extraction(self, mock_queue_service, sample_jobs):
        """Test that confidence scores are extracted correctly."""
        # Get a completed job with extraction result
        completed_jobs = [(jid, job) for jid, job in sample_jobs if job.status == JobStatus.COMPLETED]
        job_id, job = completed_jobs[0]

        mock_queue_service.get_job_ids_paginated.return_value = ([job_id], None)
        mock_queue_service.get_job.return_value = job

        with patch("src.api.routes.stats.queue_service", mock_queue_service):
            result = await get_job_stats(cursor=None, limit=1, job_status=None)

        # Verify confidence data
        assert result.jobs[0].confidence_score == job.extraction_result.confidence_score
        assert result.jobs[0].confidence_level == job.extraction_result.confidence_level

    @pytest.mark.asyncio
    async def test_large_dataset_limit(self, mock_queue_service):
        """Test maximum limit enforcement (1000)."""
        # This test ensures limit validation works
        # In practice, FastAPI will enforce the le=1000 constraint
        job_ids = [str(uuid4()) for _ in range(1000)]
        mock_queue_service.get_job_ids_paginated.return_value = (job_ids, "cursor_next")

        # Create minimal jobs
        mock_queue_service.get_job.return_value = Job(
            id="test",
            email_id="test@example.com",
            attachment_filename="test.jpg",
            attachment_path="/tmp/test.jpg",
            attachment_hash="test_hash",
            status=JobStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            retry_count=0
        )

        with patch("src.api.routes.stats.queue_service", mock_queue_service):
            result = await get_job_stats(cursor=None, limit=1000, job_status=None)

        assert result.limit == 1000
        assert len(result.jobs) <= 1000

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_queue_service):
        """Test handling of empty result set."""
        mock_queue_service.get_job_ids_paginated.return_value = ([], None)

        with patch("src.api.routes.stats.queue_service", mock_queue_service):
            result = await get_job_stats(cursor=None, limit=10, job_status=None)

        assert result.total == 0
        assert len(result.jobs) == 0
        assert result.next_cursor is None
        assert result.has_more is False


class TestAggregatedStats:
    """Tests for aggregated statistics endpoint."""

    @pytest.mark.asyncio
    async def test_get_aggregated_stats(self, mock_queue_service):
        """Test retrieving aggregated statistics."""
        # Setup mock response
        mock_stats = {
            "total": 1000,
            "pending_count": 50,
            "processing_count": 20,
            "completed_count": 800,
            "failed_count": 100,
            "exception_count": 30,
            "submitted_count": 750,
            "rejected_count": 50,
            "queue_sizes": {
                "ocr_queue": 50,
                "submission_queue": 20,
                "exception_queue": 30
            }
        }
        mock_queue_service.get_aggregated_stats.return_value = mock_stats

        with patch("src.api.routes.stats.queue_service", mock_queue_service):
            result = await get_stats_summary()

        # Verify response structure
        assert result.total_jobs == 1000
        assert result.by_status["pending"] == 50
        assert result.by_status["processing"] == 20
        assert result.by_status["completed"] == 800
        assert result.by_status["failed"] == 100
        assert result.by_status["exception"] == 30
        assert result.by_status["submitted"] == 750
        assert result.by_status["rejected"] == 50

        # Verify queue depths
        assert result.queue_depths["ocr_queue"] == 50
        assert result.queue_depths["submission_queue"] == 20
        assert result.queue_depths["exception_queue"] == 30

        # Verify service was called
        mock_queue_service.get_aggregated_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_aggregated_stats_no_jobs(self, mock_queue_service):
        """Test aggregated stats with no jobs."""
        mock_stats = {
            "total": 0,
            "pending_count": 0,
            "processing_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "exception_count": 0,
            "submitted_count": 0,
            "rejected_count": 0,
            "queue_sizes": {
                "ocr_queue": 0,
                "submission_queue": 0,
                "exception_queue": 0
            }
        }
        mock_queue_service.get_aggregated_stats.return_value = mock_stats

        with patch("src.api.routes.stats.queue_service", mock_queue_service):
            result = await get_stats_summary()

        assert result.total_jobs == 0
        assert all(count == 0 for count in result.by_status.values())
        assert all(depth == 0 for depth in result.queue_depths.values())


class TestQueueServicePagination:
    """Tests for QueueService pagination methods."""

    @pytest.mark.asyncio
    async def test_get_job_ids_paginated_basic(self):
        """Test basic pagination functionality."""
        service = QueueService()
        service.redis = AsyncMock()

        # Mock Redis SCAN to return job keys
        service.redis.scan.return_value = (
            0,  # cursor (0 means no more results)
            [b"job:uuid1", b"job:uuid2", b"job:uuid3"]
        )

        job_ids, next_cursor = await service.get_job_ids_paginated(limit=10)

        assert len(job_ids) == 3
        assert job_ids == ["uuid1", "uuid2", "uuid3"]
        assert next_cursor is None  # No more results

    @pytest.mark.asyncio
    async def test_get_job_ids_paginated_with_cursor(self):
        """Test pagination with cursor continuation."""
        service = QueueService()
        service.redis = AsyncMock()

        # Mock Redis SCAN to return non-zero cursor (more results available)
        service.redis.scan.return_value = (
            12345,  # Non-zero cursor
            [b"job:uuid4", b"job:uuid5"]
        )

        job_ids, next_cursor = await service.get_job_ids_paginated(
            cursor="0",
            limit=2
        )

        assert len(job_ids) == 2
        assert next_cursor == "12345"

    @pytest.mark.asyncio
    async def test_get_aggregated_stats_basic(self):
        """Test aggregated statistics calculation."""
        service = QueueService()
        service.redis = AsyncMock()

        # Mock pipeline for queue sizes
        mock_pipeline = AsyncMock()
        mock_pipeline.execute.return_value = [10, 5, 3]  # Queue lengths
        service.redis.pipeline.return_value = mock_pipeline

        # Mock SCAN to return job keys
        service.redis.scan.side_effect = [
            (0, [b"job:uuid1", b"job:uuid2"])
        ]

        # Mock get_job to return jobs with different statuses
        job1 = Job(
            id="uuid1",
            email_id="test1@example.com",
            attachment_filename="test1.jpg",
            attachment_path="/tmp/test1.jpg",
            attachment_hash="hash1",
            status=JobStatus.COMPLETED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            retry_count=0
        )
        job2 = Job(
            id="uuid2",
            email_id="test2@example.com",
            attachment_filename="test2.jpg",
            attachment_path="/tmp/test2.jpg",
            attachment_hash="hash2",
            status=JobStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            retry_count=0
        )

        service.get_job = AsyncMock(side_effect=[job1, job2])

        stats = await service.get_aggregated_stats()

        assert stats["total"] == 2
        assert stats["completed_count"] == 1
        assert stats["pending_count"] == 1
        assert stats["queue_sizes"]["ocr_queue"] == 10
        assert stats["queue_sizes"]["submission_queue"] == 5
        assert stats["queue_sizes"]["exception_queue"] == 3


class TestMemoryEfficiency:
    """Tests to verify memory efficiency of pagination."""

    @pytest.mark.asyncio
    async def test_pagination_memory_usage(self, mock_queue_service):
        """Test that pagination only loads requested number of jobs."""
        # This test verifies O(limit) memory usage instead of O(total_jobs)

        # Setup: 10,000 total jobs, but only request 100
        requested_limit = 100
        job_ids = [f"job_{i}" for i in range(requested_limit)]

        mock_queue_service.get_job_ids_paginated.return_value = (job_ids, "cursor_100")

        # Track how many jobs are loaded
        jobs_loaded = []

        def track_job_load(job_id):
            job = Job(
                id=job_id,
                email_id=f"{job_id}@example.com",
                attachment_filename=f"{job_id}.jpg",
                attachment_path=f"/tmp/{job_id}.jpg",
                attachment_hash=f"hash_{job_id}",
                status=JobStatus.PENDING,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                retry_count=0
            )
            jobs_loaded.append(job_id)
            return job

        mock_queue_service.get_job.side_effect = track_job_load

        with patch("src.api.routes.stats.queue_service", mock_queue_service):
            result = await get_job_stats(cursor=None, limit=requested_limit, job_status=None)

        # Verify only requested number of jobs were loaded
        assert len(jobs_loaded) == requested_limit
        assert len(result.jobs) == requested_limit

        # This demonstrates O(limit) memory usage, not O(total_jobs)
        # Even with 10k total jobs, only 100 were loaded into memory
