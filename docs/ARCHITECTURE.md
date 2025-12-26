# System Architecture
**Claims Data Entry Agent - Technical Architecture**

## Overview

The Claims Data Entry Agent is a production-ready system that automates claim data extraction from emails and generates structured JSON for the NCB core processing system.

## System Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CLAIMS DATA ENTRY AGENT                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  Gmail API   │───▶│Email Watch   │───▶│    Redis     │          │
│  │  (Pub/Sub)   │    │  Listener    │    │    Queue     │          │
│  └──────────────┘    └──────────────┘    └──────┬───────┘          │
│                                                   │                  │
│                                                   ▼                  │
│                                          ┌──────────────┐            │
│                                          │ OCR Processor│            │
│  ┌──────────────┐    ┌──────────────┐   │ PaddleOCR-VL │            │
│  │  NCB Output  │◀───│ NCB JSON Gen │◀──│  (GPU/CPU)   │            │
│  │   (Files)    │    │    Worker    │   └──────┬───────┘            │
│  └──────┬───────┘    └──────┬───────┘          │                    │
│         │                   │                  │                    │
│         │                   ▼                  ▼                    │
│         │            ┌──────────────┐   ┌──────────────┐            │
│         │            │Google Sheets │   │Google Drive  │            │
│         │            │ (Audit Log)  │   │  (Archive)   │            │
│         │            └──────────────┘   └──────────────┘            │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────┐    ┌──────────────┐                              │
│  │  Exception   │    │    Admin     │                              │
│  │    Queue     │    │  Dashboard   │                              │
│  └──────────────┘    └──────────────┘                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Email Watch Listener
**Purpose:** Real-time email monitoring via Gmail Push Notifications

**Technology:**
- Gmail API with Pub/Sub integration
- OAuth 2.0 authentication
- Asynchronous event processing

**Key Features:**
- Zero-polling design (push-based)
- Automatic OAuth token refresh
- Duplicate message detection
- Graceful error handling

**File:** `src/workers/email_watch_listener.py`

---

### 2. OCR Processor
**Purpose:** Extract text and data from receipt images

**Technology:**
- PaddleOCR-VL (Vision-Language Model, 0.9B parameters)
- GPU acceleration (CUDA 11.8+)
- Multi-language support (English, Malay, Chinese, Tamil)

**Processing Flow:**
1. Receive job from Redis queue
2. Load image (JPEG, PNG, PDF)
3. Run OCR extraction
4. Parse and structure data
5. Calculate confidence scores
6. Route based on confidence

**Confidence Routing:**
- ≥90%: Auto-submit (HIGH confidence)
- 75-89%: Submit with review flag (MEDIUM confidence)
- <75%: Route to exception queue (LOW confidence)

**File:** `src/workers/ocr_processor.py`

---

### 3. NCB JSON Generator
**Purpose:** Generate NCB-compatible JSON output files

**Output Schema:**
```json
{
  "Event date": "2024-12-21",
  "Submission Date": "2024-12-21T10:30:00.000Z",
  "Claim Amount": 150.50,
  "Invoice Number": "INV-12345",
  "Policy Number": "POL-98765"
}
```

**Features:**
- Schema validation with Pydantic
- Automatic field mapping
- Fallback logic for missing fields
- File-based output (no API submission in v1.0)

**File:** `src/workers/ncb_json_generator.py`

---

### 4. Redis Queue System
**Purpose:** Job orchestration and deduplication

**Queues:**
- `claims:ocr_queue` - Pending OCR jobs
- `claims:submission_queue` - NCB submission jobs
- `claims:exception_queue` - Low-confidence extractions

**Features:**
- SHA-256 hash-based deduplication
- 30-day TTL for processed attachments
- Atomic operations for thread safety
- Job status tracking

**File:** `src/services/queue_service.py`

---

### 5. Google Sheets Audit Log
**Purpose:** Complete audit trail for all extractions

**Schema:**
- Timestamp, Email ID, Attachment Hash
- OCR confidence score
- Extracted fields (JSON)
- NCB output filename
- Processing status

**File:** `src/services/sheets_service.py`

---

### 6. Google Drive Archive
**Purpose:** Long-term storage of original attachments

**Organization:**
```
/Claims Archive/
  └── YYYY/
      └── MM/
          └── DD/
              └── {email_id}_{attachment_name}
```

**File:** `src/services/drive_service.py`

---

### 7. Admin Dashboard (FastAPI)
**Purpose:** Health monitoring and exception queue management

**Endpoints:**
- `GET /health` - Basic health check
- `GET /health/detailed` - Component health status
- `GET /api/v1/jobs` - Job listing
- `GET /api/v1/exceptions` - Exception queue
- `GET /api/v1/stats` - Processing statistics

**File:** `src/main.py`

---

## Data Flow

### Happy Path (High Confidence)
```
1. Email arrives with attachment
   └─> Gmail sends Pub/Sub notification

2. Email Watch Listener processes notification
   └─> Downloads attachment
   └─> Computes SHA-256 hash
   └─> Checks for duplicate

3. If not duplicate:
   └─> Creates job in ocr_queue
   └─> Archives to Google Drive

4. OCR Processor dequeues job
   └─> Runs PaddleOCR-VL
   └─> Extracts text
   └─> Parses structured fields
   └─> Calculates confidence: 95%

5. High confidence (≥90%):
   └─> Routes to submission_queue

6. NCB JSON Generator processes job
   └─> Maps fields to NCB schema
   └─> Generates JSON file
   └─> Saves to ncb_output/
   └─> Logs to Google Sheets

7. Marks email as processed
```

### Exception Path (Low Confidence)
```
4. OCR Processor calculates confidence: 65%

5. Low confidence (<75%):
   └─> Routes to exception_queue
   └─> Logs to Google Sheets with "MANUAL_REVIEW" flag

6. Human reviewer accesses exception queue
   └─> Reviews OCR output
   └─> Corrects/confirms data
   └─> Resubmits or rejects
```

---

## Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| **Runtime** | Python | 3.10+ |
| **API Framework** | FastAPI | 0.104+ |
| **OCR Engine** | PaddleOCR-VL | 0.9B |
| **ML Framework** | PaddlePaddle GPU | 2.5+ |
| **Queue** | Redis | 7.0+ |
| **Container** | Docker | 24+ |
| **GPU** | NVIDIA CUDA | 11.8+ |
| **OS** | Ubuntu/Debian | 20.04+ |

---

## Deployment Architecture

### Development (docker-compose.yml)
```
┌─────────────────────────────────────┐
│  Single Container (claims-app)      │
│  ├─ FastAPI App                     │
│  ├─ Email Watch Listener (worker)   │
│  ├─ OCR Processor (worker)          │
│  └─ NCB JSON Generator (worker)     │
│                                      │
│  Network: host mode                 │
│  Redis: Host Redis (localhost:6379) │
│  GPU: Optional                      │
└─────────────────────────────────────┘
```

### Production (docker-compose.prod.yml)
```
┌─────────────────────────────────────┐
│  Main App (claims-app-prod)         │
│  ├─ FastAPI App (port 8080)         │
│  ├─ Email Watch Listener            │
│  ├─ OCR Processor (GPU-enabled)     │
│  └─ NCB JSON Generator              │
│                                      │
│  GPU: RTX 5090 with Blackwell opts  │
│  Network: host mode                 │
│  Redis: Host Redis (localhost:6379) │
│  Resources: 4 CPU, 8GB RAM          │
└─────────────────────────────────────┘

Optional Scaling (Not Enabled):
┌─────────────────────────────────────┐
│  ocr-worker x2 (Separate)           │
│  └─ OCR Processing Only             │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│  submission-worker (Separate)       │
│  └─ NCB Submission Only             │
└─────────────────────────────────────┘
```

---

## Security

### Authentication
- **Gmail:** OAuth 2.0 with token refresh
- **Google Sheets:** Service Account
- **Google Drive:** Service Account
- **Admin API:** API key middleware

### Data Protection
- **On-premise OCR:** No external AI services
- **Credentials:** Environment variables + secrets/
- **No PHI in logs:** Structured logging with field masking
- **Attachment cleanup:** 24-hour TTL for temp files

### Network Security
- **Production:** localhost binding only (reverse proxy required)
- **API:** Rate limiting with slowapi
- **Container:** Read-only filesystem where possible
- **no-new-privileges** security option

---

## Performance

### Targets
- **Email to JSON:** <5 minutes
- **OCR Processing:** 10-30 seconds per image
- **Throughput:** 500+ claims/day
- **Accuracy:** ≥95% for amounts

### Optimizations
- **GPU Acceleration:** 10-20x faster than CPU
- **Batch Processing:** Process multiple images in parallel
- **Redis Caching:** Deduplication prevents reprocessing
- **Async I/O:** Non-blocking operations throughout

### GPU Support
**Blackwell (RTX 5090):**
- Automatic detection and optimization
- PYTORCH_CUDA_ALLOC_CONF tuning
- Expanded shared memory (16GB)

**Other GPUs:**
- Ada Lovelace (RTX 40 series)
- Ampere (RTX 30 series)
- Turing (RTX 20 series)
- CPU fallback if no GPU

---

## Monitoring & Observability

### Health Checks
```bash
# Basic health
curl http://localhost:8080/health

# Detailed component status
curl http://localhost:8080/health/detailed

# Worker status
curl http://localhost:8080/health/detailed | jq '.workers'
```

### Logs
- **Format:** JSON (production), Console (development)
- **Location:** Docker stdout + /app/logs/
- **Rotation:** 50MB max, 10 files
- **Compression:** Enabled

### Metrics (Optional)
- **Prometheus endpoint:** http://localhost:9090/metrics
- **Metrics:** Job counts, processing times, error rates

---

## Error Handling

### Retry Strategy
- **Transient failures:** Exponential backoff (1s, 2s, 4s, 8s)
- **Rate limits:** Respect Retry-After headers
- **Circuit breaker:** Opens after 5 consecutive failures
- **Max retries:** 3 attempts

### Fallback Behavior
1. **OCR fails:** Log to exception queue, preserve original
2. **Google Sheets unavailable:** Log locally, retry async
3. **Drive unavailable:** Keep attachment in temp, retry
4. **Redis down:** Crash and restart (stateless workers)

---

## Scalability

### Horizontal Scaling
**Current:** Single container with embedded workers
**Future:** Separate worker containers

```bash
# Scale OCR workers for high volume
docker compose -f docker-compose.prod.yml up -d --scale ocr-worker=3

# Scale submission workers
docker compose -f docker-compose.prod.yml up -d --scale submission-worker=2
```

### Vertical Scaling
- **CPU:** 2-4 cores recommended
- **Memory:** 4-8GB recommended
- **GPU:** Single GPU sufficient for 500+ claims/day
- **Disk:** 50GB minimum

---

## Development vs Production

| Aspect | Development | Production |
|--------|-------------|------------|
| **Environment** | APP_ENV=development | APP_ENV=production |
| **Logging** | Console, DEBUG | JSON, WARNING |
| **GPU** | Optional | Enabled |
| **Volumes** | Hot-reload mounted | Data only |
| **Redis** | Host Redis | Host Redis |
| **Health Checks** | Basic | Comprehensive |
| **Restart Policy** | unless-stopped | always |

---

## File Structure

```
src/
├── main.py                    # FastAPI app + worker lifecycle
├── config/
│   └── settings.py            # Pydantic Settings (all config)
├── models/
│   ├── claim.py               # Claim data models
│   ├── extraction.py          # OCR extraction models
│   ├── job.py                 # Job/task models
│   └── email.py               # Email metadata models
├── services/
│   ├── email_service.py       # Gmail API integration
│   ├── ocr_service.py         # PaddleOCR-VL wrapper
│   ├── ncb_service.py         # NCB API client (future)
│   ├── sheets_service.py      # Google Sheets logging
│   ├── drive_service.py       # Google Drive archiving
│   └── queue_service.py       # Redis queue management
├── workers/
│   ├── email_watch_listener.py   # Gmail Pub/Sub listener
│   ├── ocr_processor.py          # OCR extraction worker
│   └── ncb_json_generator.py     # NCB JSON output worker
├── api/
│   ├── routes/
│   │   ├── jobs.py               # Job management endpoints
│   │   ├── exceptions.py         # Exception queue endpoints
│   │   └── stats.py              # Statistics endpoints
│   └── middleware/
│       ├── auth.py               # API key authentication
│       ├── logging.py            # Request logging
│       └── rate_limit.py         # Rate limiting
└── utils/
    ├── logging.py                # Structured logging setup
    ├── deduplication.py          # Hash-based duplicate detection
    └── confidence.py             # OCR confidence scoring
```

---

## Configuration

All configuration via environment variables (see `.env.example`):

**Critical Variables:**
- `GOOGLE_CLOUD_PROJECT_ID` - GCP project for Pub/Sub
- `GMAIL_CREDENTIALS_PATH` - OAuth credentials
- `GMAIL_TOKEN_PATH` - OAuth token (auto-refreshed)
- `REDIS_URL` - Redis connection string
- `OCR_USE_GPU` - Enable GPU acceleration

**See:** `.env.example` for complete list

---

## Testing

- **Unit Tests:** 97 tests (src/services, src/models)
- **Integration Tests:** 28 tests (API endpoints, workers)
- **E2E Tests:** 17 tests (100% passing)
- **Coverage:** 24% (target: 80%)

**Run Tests:**
```bash
# All tests
pytest tests/ -v

# With coverage
pytest --cov=src --cov-report=html tests/

# E2E only
pytest tests/e2e/ -v
```

---

**For more details:**
- Deployment Guide: `docs/DEPLOYMENT.md`
- Docker Guide: `docs/DOCKER.md`
- NCB Schema: `docs/NCB_SCHEMA_UPDATE.md`
- GPU Setup: `docs/BLACKWELL_GPU.md`
