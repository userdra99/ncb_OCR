# Technical Specification
## Claims Data Entry Agent

**Version:** 1.0  
**Last Updated:** December 2024

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLAIMS DATA ENTRY AGENT                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   Gmail API  │───▶│ Email Poller │───▶│    Redis     │───▶│    OCR    │ │
│  │   (Inbound)  │    │   Worker     │    │    Queue     │    │  Worker   │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └─────┬─────┘ │
│                                                                     │       │
│                                          ┌──────────────────────────┘       │
│                                          ▼                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   NCB API    │◀───│  Submitter   │◀───│ PaddleOCR-VL │                  │
│  │   (Core)     │    │   Worker     │    │   (0.9B)     │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│         │                   │                                               │
│         │                   ▼                                               │
│         │            ┌──────────────┐    ┌──────────────┐                  │
│         │            │ Google Sheets│    │ Google Drive │                  │
│         │            │   (Backup)   │    │  (Archive)   │                  │
│         │            └──────────────┘    └──────────────┘                  │
│         │                                                                   │
│         ▼                                                                   │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │  Exception   │◀───│    Admin     │                                      │
│  │    Queue     │    │  Dashboard   │                                      │
│  └──────────────┘    └──────────────┘                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| Email Poller Worker | Monitor inbox, download attachments, create jobs |
| Redis Queue | Job queuing, deduplication, status tracking |
| OCR Worker | Extract text using PaddleOCR-VL, structure data |
| Submitter Worker | Submit to NCB API, handle retries |
| Google Sheets Service | Log all extractions for audit |
| Google Drive Service | Archive original attachments |
| Admin Dashboard | Monitoring, exception handling, manual review |

### 1.3 Data Flow

```
1. Email arrives in claims inbox
2. Email Poller detects new email with attachments
3. Attachments downloaded to temp storage
4. Job created in Redis queue (status: PENDING)
5. OCR Worker picks up job
6. PaddleOCR-VL extracts text from images
7. Extraction mapped to NCB schema
8. Confidence score calculated
9. If confidence ≥ threshold:
   a. Job queued for NCB submission
   b. Submitter posts to NCB API
   c. NCB reference captured
10. If confidence < threshold:
    a. Job routed to exception queue
    b. Staff notified for manual review
11. All extractions logged to Google Sheets
12. Attachments archived to Google Drive
13. Email marked as processed
```

---

## 2. Technology Stack

### 2.1 Core Technologies

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Language | Python | 3.10+ | Primary runtime |
| Web Framework | FastAPI | 0.104+ | REST API, async support |
| Queue | Redis | 7.0+ | Job queue, caching |
| OCR | PaddleOCR-VL | 0.9B | Vision-language extraction |
| ML Framework | PaddlePaddle | 2.5+ | OCR backend |
| Container | Docker | 24+ | Deployment |
| GPU | CUDA | 11.8+ | GPU acceleration |

### 2.2 Python Dependencies

```txt
# Core
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0

# Queue
redis>=5.0.0
rq>=1.15.0

# OCR
paddlepaddle-gpu>=2.5.0
paddleocr>=2.7.0

# Google APIs
google-api-python-client>=2.100.0
google-auth-httplib2>=0.1.0
google-auth-oauthlib>=1.1.0
gspread>=5.12.0

# Image Processing
Pillow>=10.0.0
pdf2image>=1.16.0
opencv-python>=4.8.0

# Utilities
httpx>=0.25.0
structlog>=23.2.0
tenacity>=8.2.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
```

### 2.3 Infrastructure Requirements

**Minimum Hardware:**
| Component | Specification |
|-----------|---------------|
| CPU | Intel Core i5-9500 / AMD Ryzen 5 3600 |
| RAM | 16 GB DDR4 |
| GPU | NVIDIA RTX 2060 (6 GB VRAM) |
| Storage | 50 GB SSD |
| Network | Stable internet for API calls |

**Recommended Hardware:**
| Component | Specification |
|-----------|---------------|
| CPU | Intel Core i7-10700 / AMD Ryzen 7 5800X |
| RAM | 32 GB DDR4 |
| GPU | NVIDIA RTX 3060/4060 (8-12 GB VRAM) |
| Storage | 100 GB NVMe SSD |
| Network | Gigabit ethernet |

---

## 3. Data Models

### 3.1 Core Models

```python
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    SUBMITTED = "submitted"
    EXCEPTION = "exception"
    FAILED = "failed"

class ConfidenceLevel(str, Enum):
    HIGH = "high"      # ≥90%
    MEDIUM = "medium"  # 75-89%
    LOW = "low"        # <75%

class ExtractedClaim(BaseModel):
    """Structured claim data extracted from receipt"""
    member_id: Optional[str] = None
    member_name: Optional[str] = None
    provider_name: Optional[str] = None
    provider_address: Optional[str] = None
    service_date: Optional[datetime] = None
    receipt_number: Optional[str] = None
    total_amount: Optional[float] = None
    currency: str = "MYR"
    itemized_charges: Optional[list[dict]] = None
    gst_amount: Optional[float] = None
    sst_amount: Optional[float] = None
    raw_text: str = ""
    
class ExtractionResult(BaseModel):
    """OCR extraction result with confidence"""
    claim: ExtractedClaim
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    field_confidences: dict[str, float] = {}
    warnings: list[str] = []
    
class Job(BaseModel):
    """Processing job"""
    id: str
    email_id: str
    attachment_filename: str
    attachment_path: str
    attachment_hash: str
    status: JobStatus = JobStatus.PENDING
    extraction_result: Optional[ExtractionResult] = None
    ncb_reference: Optional[str] = None
    ncb_submitted_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    created_at: datetime
    updated_at: datetime
    
class EmailMetadata(BaseModel):
    """Email metadata"""
    message_id: str
    sender: str
    subject: str
    received_at: datetime
    attachments: list[str]
    labels: list[str] = []
```

### 3.2 API Request/Response Models

```python
class NCBSubmissionRequest(BaseModel):
    """Request payload for NCB API"""
    member_id: str
    member_name: str
    provider_name: str
    provider_address: Optional[str] = None
    service_date: str  # ISO format
    receipt_number: str
    total_amount: float
    currency: str = "MYR"
    itemized_charges: Optional[list[dict]] = None
    gst_amount: Optional[float] = None
    sst_amount: Optional[float] = None
    source_email_id: str
    source_filename: str
    extraction_confidence: float
    
class NCBSubmissionResponse(BaseModel):
    """Response from NCB API"""
    success: bool
    claim_reference: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
class JobResponse(BaseModel):
    """API response for job status"""
    id: str
    status: JobStatus
    email_id: str
    filename: str
    confidence_score: Optional[float] = None
    ncb_reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
class DashboardStats(BaseModel):
    """Dashboard statistics"""
    total_processed_today: int
    total_processed_week: int
    total_processed_month: int
    success_rate: float
    average_confidence: float
    pending_exceptions: int
    ncb_submission_rate: float
    average_processing_time_seconds: float
```

---

## 4. Service Specifications

### 4.1 Email Service

```python
class EmailService:
    """Gmail API integration"""
    
    async def poll_inbox(self) -> list[EmailMetadata]:
        """
        Poll inbox for unread emails with attachments
        
        Returns:
            List of email metadata for new emails
            
        Filters:
            - Has attachments
            - Is unread
            - Not in processed label
        """
        
    async def download_attachment(
        self, 
        message_id: str, 
        attachment_id: str,
        destination: Path
    ) -> Path:
        """
        Download attachment to local storage
        
        Args:
            message_id: Gmail message ID
            attachment_id: Attachment ID within message
            destination: Local path for download
            
        Returns:
            Path to downloaded file
        """
        
    async def mark_as_processed(self, message_id: str) -> None:
        """Mark email as read and apply processed label"""
        
    async def get_message_body(self, message_id: str) -> str:
        """Extract plain text body from email"""
```

**Configuration:**
```python
class EmailConfig(BaseSettings):
    gmail_credentials_path: Path
    gmail_token_path: Path
    inbox_label: str = "INBOX"
    processed_label: str = "Claims/Processed"
    poll_interval_seconds: int = 30
    max_attachment_size_mb: int = 25
```

### 4.2 OCR Service

```python
class OCRService:
    """PaddleOCR-VL integration"""
    
    def __init__(self, config: OCRConfig):
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang=config.default_language,
            use_gpu=config.use_gpu,
            show_log=False,
            det_db_thresh=config.detection_threshold,
            rec_batch_num=config.batch_size
        )
        
    async def extract_text(self, image_path: Path) -> OCRResult:
        """
        Extract raw text from image
        
        Args:
            image_path: Path to image file
            
        Returns:
            OCRResult with text blocks and positions
        """
        
    async def extract_structured_data(
        self, 
        image_path: Path
    ) -> ExtractionResult:
        """
        Extract and structure claim data from receipt image
        
        Args:
            image_path: Path to receipt image
            
        Returns:
            ExtractionResult with structured claim and confidence
        """
        
    def calculate_confidence(
        self, 
        ocr_result: OCRResult,
        extracted: ExtractedClaim
    ) -> tuple[float, dict[str, float]]:
        """
        Calculate overall and per-field confidence scores
        
        Returns:
            Tuple of (overall_score, field_scores_dict)
        """
```

**Configuration:**
```python
class OCRConfig(BaseSettings):
    use_gpu: bool = True
    default_language: str = "en"
    supported_languages: list[str] = ["en", "ch", "ms", "ta"]
    detection_threshold: float = 0.5
    recognition_threshold: float = 0.5
    batch_size: int = 6
    max_image_size: int = 4096
    
    # Confidence thresholds
    high_confidence_threshold: float = 0.90
    medium_confidence_threshold: float = 0.75
```

### 4.3 NCB Service

```python
class NCBService:
    """NCB API integration"""
    
    async def submit_claim(
        self, 
        claim: NCBSubmissionRequest
    ) -> NCBSubmissionResponse:
        """
        Submit extracted claim data to NCB
        
        Args:
            claim: Structured claim data
            
        Returns:
            Submission response with claim reference
            
        Raises:
            NCBConnectionError: If API unreachable
            NCBValidationError: If data validation fails
            NCBRateLimitError: If rate limited
        """
        
    async def check_health(self) -> bool:
        """Check if NCB API is available"""
        
    async def get_claim_status(
        self, 
        reference: str
    ) -> dict:
        """Get status of submitted claim"""
```

**Configuration:**
```python
class NCBConfig(BaseSettings):
    api_base_url: str
    api_key: SecretStr
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_backoff_base: float = 2.0
    retry_backoff_max: float = 60.0
```

### 4.4 Sheets Service

```python
class SheetsService:
    """Google Sheets backup logging"""
    
    async def log_extraction(
        self, 
        job: Job,
        extraction: ExtractionResult
    ) -> str:
        """
        Log extraction to Google Sheets
        
        Args:
            job: Processing job
            extraction: Extraction result
            
        Returns:
            Sheet row reference
        """
        
    async def update_ncb_status(
        self, 
        row_ref: str,
        ncb_reference: str,
        status: str
    ) -> None:
        """Update row with NCB submission status"""
        
    async def get_daily_summary(
        self, 
        date: datetime.date
    ) -> dict:
        """Get processing summary for date"""
```

**Sheet Schema:**
| Column | Type | Description |
|--------|------|-------------|
| A | datetime | Processing timestamp |
| B | string | Email ID |
| C | string | Sender |
| D | string | Attachment filename |
| E | string | Member ID (extracted) |
| F | string | Provider name (extracted) |
| G | float | Amount (extracted) |
| H | float | Confidence score |
| I | string | Status |
| J | string | NCB reference |
| K | datetime | NCB submission time |
| L | string | Error message (if any) |

### 4.5 Drive Service

```python
class DriveService:
    """Google Drive archive"""
    
    async def archive_attachment(
        self, 
        local_path: Path,
        email_id: str,
        original_filename: str
    ) -> str:
        """
        Archive attachment to Google Drive
        
        Args:
            local_path: Path to local file
            email_id: Source email ID
            original_filename: Original attachment name
            
        Returns:
            Google Drive file ID
            
        Folder structure:
            /claims/{YYYY}/{MM}/{DD}/{email_id}_{filename}
        """
        
    async def get_file_url(self, file_id: str) -> str:
        """Get shareable URL for archived file"""
```

### 4.6 Queue Service

```python
class QueueService:
    """Redis job queue management"""
    
    async def enqueue_job(self, job: Job) -> str:
        """Add job to processing queue"""
        
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        
    async def update_job_status(
        self, 
        job_id: str, 
        status: JobStatus,
        **kwargs
    ) -> None:
        """Update job status and optional fields"""
        
    async def get_pending_jobs(self) -> list[Job]:
        """Get all pending jobs"""
        
    async def get_exception_queue(self) -> list[Job]:
        """Get jobs in exception status"""
        
    async def check_duplicate(self, file_hash: str) -> bool:
        """Check if attachment already processed"""
        
    async def record_hash(
        self, 
        file_hash: str, 
        job_id: str
    ) -> None:
        """Record file hash for deduplication"""
```

---

## 5. Worker Specifications

### 5.1 Email Poller Worker

```python
class EmailPollerWorker:
    """
    Monitors Gmail inbox for new claim emails
    
    Runs continuously, polling at configured interval
    """
    
    async def run(self) -> None:
        """Main worker loop"""
        while True:
            try:
                emails = await self.email_service.poll_inbox()
                for email in emails:
                    await self.process_email(email)
            except Exception as e:
                logger.error("Polling error", error=str(e))
            await asyncio.sleep(self.config.poll_interval)
            
    async def process_email(self, email: EmailMetadata) -> None:
        """
        Process single email:
        1. Download attachments
        2. Compute hashes
        3. Check for duplicates
        4. Create jobs
        5. Mark email processed
        """
```

### 5.2 OCR Processor Worker

```python
class OCRProcessorWorker:
    """
    Processes images through OCR pipeline
    
    Pulls jobs from queue, extracts data, updates status
    """
    
    async def run(self) -> None:
        """Main worker loop"""
        while True:
            job = await self.queue.dequeue("ocr_queue")
            if job:
                await self.process_job(job)
            else:
                await asyncio.sleep(1)
                
    async def process_job(self, job: Job) -> None:
        """
        Process single job:
        1. Load image
        2. Run OCR extraction
        3. Structure data
        4. Calculate confidence
        5. Route based on confidence
        6. Log to Sheets
        7. Archive to Drive
        """
```

### 5.3 NCB Submitter Worker

```python
class NCBSubmitterWorker:
    """
    Submits extracted claims to NCB API
    
    Handles retries, failures, and fallback
    """
    
    async def run(self) -> None:
        """Main worker loop"""
        while True:
            job = await self.queue.dequeue("submission_queue")
            if job:
                await self.submit_job(job)
            else:
                await asyncio.sleep(1)
                
    async def submit_job(self, job: Job) -> None:
        """
        Submit single job:
        1. Build NCB request
        2. Attempt submission
        3. Handle response
        4. Update job status
        5. Update Sheets
        """
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, max=60),
        retry=retry_if_exception_type(NCBConnectionError)
    )
    async def submit_with_retry(
        self, 
        request: NCBSubmissionRequest
    ) -> NCBSubmissionResponse:
        """Submit with exponential backoff retry"""
```

---

## 6. API Endpoints

### 6.1 Health & Status

```
GET /health
Response: { "status": "healthy", "version": "1.0.0" }

GET /health/detailed
Response: {
    "status": "healthy",
    "components": {
        "redis": "connected",
        "gmail": "connected",
        "ncb": "connected",
        "sheets": "connected",
        "drive": "connected"
    },
    "workers": {
        "email_poller": "running",
        "ocr_processor": "running",
        "ncb_submitter": "running"
    }
}
```

### 6.2 Jobs

```
GET /api/v1/jobs
Query params: status, limit, offset, date_from, date_to
Response: { "jobs": [...], "total": 100, "page": 1 }

GET /api/v1/jobs/{job_id}
Response: { "id": "...", "status": "...", ... }

POST /api/v1/jobs/{job_id}/retry
Response: { "success": true, "message": "Job requeued" }
```

### 6.3 Exceptions

```
GET /api/v1/exceptions
Response: { "exceptions": [...], "count": 5 }

POST /api/v1/exceptions/{job_id}/approve
Body: { "corrected_data": {...} }
Response: { "success": true, "ncb_reference": "..." }

POST /api/v1/exceptions/{job_id}/reject
Body: { "reason": "..." }
Response: { "success": true }
```

### 6.4 Statistics

```
GET /api/v1/stats/dashboard
Response: {
    "total_processed_today": 142,
    "success_rate": 0.97,
    "average_confidence": 0.962,
    "pending_exceptions": 4,
    ...
}

GET /api/v1/stats/daily?date=2024-12-18
Response: { "date": "2024-12-18", ... }
```

---

## 7. Error Handling

### 7.1 Error Categories

| Category | HTTP Code | Retry | Action |
|----------|-----------|-------|--------|
| Transient | 5xx | Yes | Exponential backoff |
| Rate limit | 429 | Yes | Wait per Retry-After |
| Validation | 400 | No | Route to exception |
| Auth | 401, 403 | No | Alert, stop processing |
| Not found | 404 | No | Log and skip |

### 7.2 Retry Strategy

```python
RETRY_CONFIG = {
    "max_attempts": 3,
    "backoff_base": 2.0,  # seconds
    "backoff_max": 60.0,  # seconds
    "backoff_jitter": 0.1,  # 10% jitter
}

# Retry on: ConnectionError, TimeoutError, 5xx responses
# No retry on: 4xx responses (except 429)
```

### 7.3 Fallback Behavior

1. **NCB unavailable**: Queue to Sheets, retry when available
2. **Sheets unavailable**: Local file backup, retry
3. **Drive unavailable**: Keep local copy, retry
4. **Gmail unavailable**: Pause polling, alert, retry

---

## 8. Logging & Monitoring

### 8.1 Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Log format
{
    "timestamp": "2024-12-18T10:42:00Z",
    "level": "info",
    "event": "job_processed",
    "job_id": "abc123",
    "email_id": "msg456",
    "confidence": 0.95,
    "duration_ms": 1234,
    "correlation_id": "req789"
}
```

### 8.2 Metrics

| Metric | Type | Description |
|--------|------|-------------|
| jobs_processed_total | Counter | Total jobs processed |
| jobs_by_status | Counter | Jobs by status |
| ocr_duration_seconds | Histogram | OCR processing time |
| extraction_confidence | Histogram | Confidence scores |
| ncb_submission_duration | Histogram | NCB API latency |
| exception_queue_size | Gauge | Current exception count |

### 8.3 Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| High exception rate | >20% in 1 hour | Warning |
| NCB unavailable | >5 min downtime | Critical |
| Processing backlog | >100 pending jobs | Warning |
| OCR failures | >10% failure rate | Warning |
| Worker stopped | Worker not responding | Critical |

---

## 9. Security Considerations

### 9.1 Data Protection

- All processing on-premise (no external AI services)
- TLS 1.3 for all API communications
- Credentials stored in environment variables
- No PHI in application logs
- Temporary files deleted after processing

### 9.2 Access Control

- Service account for Google APIs (minimal scopes)
- API key authentication for admin dashboard
- Rate limiting on all endpoints
- Input validation on all user inputs

### 9.3 Audit Trail

- Complete log of all extractions in Google Sheets
- Original documents preserved in Google Drive
- Job status history maintained in Redis
- All API calls logged with correlation IDs

---

## 10. Deployment

### 10.1 Docker Configuration

```dockerfile
# Dockerfile
FROM nvidia/cuda:11.8-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3.10 python3-pip \
    libgl1-mesa-glx libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/

ENV PYTHONPATH=/app
CMD ["python", "-m", "src.main"]
```

### 10.2 Docker Compose

```yaml
version: '3.8'

services:
  app:
    build: .
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    depends_on:
      - redis
    restart: unless-stopped
    
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped
    
  admin:
    build:
      context: .
      dockerfile: Dockerfile.admin
    ports:
      - "8080:8080"
    env_file: .env
    depends_on:
      - app
      - redis
    restart: unless-stopped

volumes:
  redis_data:
```

### 10.3 Environment Variables

```bash
# .env.example

# Application
APP_ENV=production
APP_DEBUG=false
LOG_LEVEL=INFO

# Gmail
GMAIL_CREDENTIALS_PATH=/app/secrets/gmail_credentials.json
GMAIL_TOKEN_PATH=/app/secrets/gmail_token.json
GMAIL_INBOX_LABEL=INBOX
GMAIL_POLL_INTERVAL=30

# NCB API
NCB_API_BASE_URL=https://ncb.internal.company.com/api/v1
NCB_API_KEY=your-api-key-here
NCB_TIMEOUT=30

# Google Sheets
SHEETS_CREDENTIALS_PATH=/app/secrets/sheets_credentials.json
SHEETS_SPREADSHEET_ID=your-spreadsheet-id

# Google Drive
DRIVE_CREDENTIALS_PATH=/app/secrets/drive_credentials.json
DRIVE_FOLDER_ID=your-folder-id

# Redis
REDIS_URL=redis://redis:6379/0

# OCR
OCR_USE_GPU=true
OCR_DEFAULT_LANGUAGE=en
OCR_CONFIDENCE_THRESHOLD=0.75

# Admin
ADMIN_API_KEY=your-admin-api-key
ADMIN_PORT=8080
```
