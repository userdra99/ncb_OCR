"""API request/response models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.extraction import ConfidenceLevel
from src.models.job import JobStatus


# Pagination models
class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""

    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    total_pages: int = Field(description="Total number of pages")


# Job API models
class JobListParams(BaseModel):
    """Query parameters for job listing."""

    status: Optional[JobStatus] = Field(default=None, description="Filter by job status")
    start_date: Optional[datetime] = Field(default=None, description="Filter by start date")
    end_date: Optional[datetime] = Field(default=None, description="Filter by end date")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class JobDetailResponse(BaseModel):
    """Detailed job response."""

    id: str
    email_id: str
    attachment_filename: str
    status: JobStatus
    confidence_score: Optional[float] = None
    confidence_level: Optional[ConfidenceLevel] = None
    ncb_reference: Optional[str] = None
    ncb_submitted_at: Optional[datetime] = None
    sheets_row_ref: Optional[str] = None
    drive_file_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    # Extracted claim data (if available)
    member_id: Optional[str] = None
    member_name: Optional[str] = None
    provider_name: Optional[str] = None
    service_date: Optional[datetime] = None
    total_amount: Optional[float] = None


class JobListResponse(PaginatedResponse):
    """Paginated job list response."""

    items: list[JobDetailResponse]


class JobRetryResponse(BaseModel):
    """Response for job retry operation."""

    success: bool
    job_id: str
    message: str
    new_status: JobStatus


# Exception queue models
class ExceptionListParams(BaseModel):
    """Query parameters for exception queue."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ExceptionDetailResponse(BaseModel):
    """Exception queue item detail."""

    id: str
    email_id: str
    attachment_filename: str
    confidence_score: float
    confidence_level: ConfidenceLevel
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime

    # Extracted data for review
    member_id: Optional[str] = None
    member_name: Optional[str] = None
    provider_name: Optional[str] = None
    service_date: Optional[datetime] = None
    receipt_number: Optional[str] = None
    total_amount: Optional[float] = None

    # Field-level confidence scores
    field_confidences: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ExceptionListResponse(PaginatedResponse):
    """Paginated exception list response."""

    items: list[ExceptionDetailResponse]


class ExceptionApprovalRequest(BaseModel):
    """Request to approve exception and submit to NCB."""

    override_data: Optional[dict] = Field(
        default=None,
        description="Optional corrected data to override extraction"
    )


class ExceptionApprovalResponse(BaseModel):
    """Response for exception approval."""

    success: bool
    job_id: str
    ncb_reference: Optional[str] = None
    message: str


class ExceptionRejectionRequest(BaseModel):
    """Request to reject exception."""

    reason: str = Field(description="Reason for rejection")


class ExceptionRejectionResponse(BaseModel):
    """Response for exception rejection."""

    success: bool
    job_id: str
    message: str


# Statistics models
class DashboardStatsResponse(BaseModel):
    """Dashboard summary statistics."""

    # Processing counts
    total_processed_today: int
    total_processed_week: int
    total_processed_month: int

    # Success metrics
    success_rate: float = Field(ge=0.0, le=1.0, description="Overall success rate")
    ncb_submission_rate: float = Field(ge=0.0, le=1.0, description="Auto-submission rate")

    # Quality metrics
    average_confidence: float = Field(ge=0.0, le=1.0, description="Average confidence score")
    high_confidence_count: int = Field(description="Jobs with >=90% confidence")
    medium_confidence_count: int = Field(description="Jobs with 75-89% confidence")
    low_confidence_count: int = Field(description="Jobs with <75% confidence")

    # Queue status
    pending_exceptions: int
    pending_ocr: int
    pending_submission: int

    # Performance
    average_processing_time_seconds: float

    # Status breakdown
    status_breakdown: dict[str, int] = Field(
        description="Count of jobs by status"
    )


class DailyStatsParams(BaseModel):
    """Query parameters for daily statistics."""

    start_date: datetime = Field(description="Start date for stats")
    end_date: datetime = Field(description="End date for stats")


class DailyStatsItem(BaseModel):
    """Statistics for a single day."""

    date: datetime
    total_processed: int
    successful: int
    failed: int
    exceptions: int
    average_confidence: float
    average_processing_time_seconds: float


class DailyStatsResponse(BaseModel):
    """Daily statistics breakdown."""

    items: list[DailyStatsItem]
    summary: DashboardStatsResponse


# Paginated job stats models
class JobStatItem(BaseModel):
    """Job statistics item for paginated endpoint."""

    id: str
    email_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    processing_time_ms: Optional[float] = None
    confidence_score: Optional[float] = None
    confidence_level: Optional[ConfidenceLevel] = None
    ncb_reference: Optional[str] = None


class PaginatedJobStatsResponse(BaseModel):
    """Paginated job statistics response."""

    total: int = Field(description="Total jobs matching filter")
    jobs: list[JobStatItem] = Field(description="Jobs in current page")
    next_cursor: Optional[str] = Field(description="Cursor for next page")
    has_more: bool = Field(description="Whether more results exist")
    limit: int = Field(description="Page size used")


class AggregatedStatsResponse(BaseModel):
    """Aggregated statistics without loading all jobs."""

    total_jobs: int = Field(description="Total number of jobs")
    by_status: dict[str, int] = Field(description="Job counts by status")
    queue_depths: dict[str, int] = Field(description="Current queue sizes")
    processing_times: dict[str, float] = Field(description="Average processing times by queue")
