# Development Tasks
## Claims Data Entry Agent

**Version:** 1.0  
**Last Updated:** December 2024

---

## Overview

This document breaks down the implementation into discrete, actionable tasks organized by phase. Each task includes acceptance criteria and dependencies.

**Legend:**
- 🔴 Critical Path (blocks other tasks)
- 🟡 Important (should not be skipped)
- 🟢 Nice to have (can defer if needed)

---

## Phase 1: Foundation (Weeks 1-2)

### 1.1 Project Setup 🔴

**Task 1.1.1: Initialize Project Structure**
```
Priority: 🔴 Critical
Estimated: 2 hours
Dependencies: None
```

- [ ] Create project directory structure per PROMPT.md
- [ ] Initialize git repository with .gitignore
- [ ] Create pyproject.toml with dependencies
- [ ] Create requirements.txt
- [ ] Create .env.example with all required variables
- [ ] Set up pre-commit hooks (black, ruff, mypy)

**Acceptance Criteria:**
- `pip install -e .` works
- All linters pass on empty project
- Directory structure matches specification

---

**Task 1.1.2: Docker Configuration**
```
Priority: 🔴 Critical
Estimated: 3 hours
Dependencies: 1.1.1
```

- [ ] Create Dockerfile with CUDA support
- [ ] Create docker-compose.yml for development
- [ ] Create docker-compose.prod.yml for production
- [ ] Configure volume mounts for credentials
- [ ] Test GPU passthrough

**Acceptance Criteria:**
- `docker-compose up` starts all services
- GPU is accessible inside container
- Environment variables properly injected

---

**Task 1.1.3: Configuration Management**
```
Priority: 🔴 Critical
Estimated: 2 hours
Dependencies: 1.1.1
```

- [ ] Create `src/config/settings.py` with Pydantic Settings
- [ ] Define all configuration models (OCRConfig, EmailConfig, etc.)
- [ ] Implement environment variable loading
- [ ] Add configuration validation

**Acceptance Criteria:**
- All configs load from .env
- Validation errors are clear
- Secrets handled securely (SecretStr)

---

### 1.2 Core Data Models 🔴

**Task 1.2.1: Define Pydantic Models**
```
Priority: 🔴 Critical
Estimated: 3 hours
Dependencies: 1.1.3
```

- [ ] Create `src/models/claim.py` with ExtractedClaim model
- [ ] Create `src/models/extraction.py` with ExtractionResult model
- [ ] Create `src/models/job.py` with Job and JobStatus models
- [ ] Create `src/models/email.py` with EmailMetadata model
- [ ] Add model serialization/deserialization tests

**Acceptance Criteria:**
- All models have type hints
- JSON serialization works correctly
- Validation catches invalid data

---

### 1.3 OCR Service 🔴

**Task 1.3.1: PaddleOCR-VL Setup**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: 1.1.2, 1.2.1
```

- [ ] Install PaddlePaddle with GPU support
- [ ] Install PaddleOCR
- [ ] Create `src/services/ocr_service.py`
- [ ] Implement OCR initialization with GPU
- [ ] Test with sample images

**Acceptance Criteria:**
- OCR model loads successfully
- GPU utilization confirmed
- Basic text extraction works

---

**Task 1.3.2: Text Extraction**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: 1.3.1
```

- [ ] Implement `extract_text()` method
- [ ] Handle image preprocessing (rotation, deskew)
- [ ] Support multiple image formats (JPEG, PNG, TIFF)
- [ ] Implement PDF page extraction
- [ ] Add confidence score per text block

**Acceptance Criteria:**
- Extracts text from test receipts
- Handles rotated images
- PDF pages converted correctly

---

**Task 1.3.3: Data Structuring**
```
Priority: 🔴 Critical
Estimated: 6 hours
Dependencies: 1.3.2
```

- [ ] Implement receipt field extraction patterns
- [ ] Create regex patterns for Malaysian formats
- [ ] Parse monetary amounts (RM format)
- [ ] Parse dates (DD/MM/YYYY, etc.)
- [ ] Extract provider name and address
- [ ] Map to ExtractedClaim model
- [ ] Calculate field-level confidence scores

**Acceptance Criteria:**
- Extracts all required fields from test receipts
- Amount parsing handles RM format
- Date parsing handles common Malaysian formats
- Overall confidence score calculated

---

**Task 1.3.4: Multi-language Support**
```
Priority: 🟡 Important
Estimated: 3 hours
Dependencies: 1.3.3
```

- [ ] Configure language detection
- [ ] Test English extraction
- [ ] Test Malay extraction
- [ ] Test Chinese (Simplified) extraction
- [ ] Test Tamil extraction
- [ ] Handle mixed-language receipts

**Acceptance Criteria:**
- Detects language automatically
- Accuracy maintained across languages
- Mixed-language receipts handled

---

### 1.4 Gmail Integration 🔴

**Task 1.4.1: Gmail OAuth Setup**
```
Priority: 🔴 Critical
Estimated: 3 hours
Dependencies: 1.1.3
```

- [ ] Create Google Cloud project (if needed)
- [ ] Configure OAuth consent screen
- [ ] Create service account credentials
- [ ] Create `scripts/setup_gmail.py` for token generation
- [ ] Document setup process

**Acceptance Criteria:**
- OAuth flow completes successfully
- Token persists across restarts
- Service account can access inbox

---

**Task 1.4.2: Email Service Implementation**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: 1.4.1, 1.2.1
```

- [ ] Create `src/services/email_service.py`
- [ ] Implement inbox polling
- [ ] Filter for emails with attachments
- [ ] Extract email metadata
- [ ] Download attachments to temp storage

**Acceptance Criteria:**
- Polls inbox successfully
- Identifies emails with attachments
- Downloads attachments correctly

---

**Task 1.4.3: Email Processing Logic**
```
Priority: 🔴 Critical
Estimated: 3 hours
Dependencies: 1.4.2
```

- [ ] Mark emails as read after processing
- [ ] Apply labels to processed emails
- [ ] Handle multiple attachments per email
- [ ] Extract email body for member info
- [ ] Implement error handling

**Acceptance Criteria:**
- Emails marked as processed
- Labels applied correctly
- Multiple attachments handled

---

### 1.5 NCB API Integration 🔴

**Task 1.5.1: NCB API Discovery**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: None (external dependency)
```

- [ ] Schedule discovery session with NCB team
- [ ] Document API endpoint(s)
- [ ] Document authentication method
- [ ] Document request/response schemas
- [ ] Document error codes
- [ ] Update API_CONTRACTS.md

**Acceptance Criteria:**
- Complete API documentation
- Sample request/response captured
- Authentication tested

---

**Task 1.5.2: NCB Service Implementation**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: 1.5.1, 1.2.1
```

- [ ] Create `src/services/ncb_service.py`
- [ ] Implement claim submission
- [ ] Implement response handling
- [ ] Capture claim reference number
- [ ] Implement retry logic with exponential backoff

**Acceptance Criteria:**
- Submissions succeed in test environment
- Reference numbers captured
- Retries work correctly

---

**Task 1.5.3: NCB Error Handling**
```
Priority: 🔴 Critical
Estimated: 3 hours
Dependencies: 1.5.2
```

- [ ] Handle validation errors (400)
- [ ] Handle auth errors (401, 403)
- [ ] Handle rate limiting (429)
- [ ] Handle server errors (5xx)
- [ ] Implement circuit breaker pattern

**Acceptance Criteria:**
- All error types handled gracefully
- Appropriate logging for each error
- Circuit breaker prevents overload

---

### 1.6 Redis Queue 🔴

**Task 1.6.1: Queue Service Implementation**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: 1.1.2, 1.2.1
```

- [ ] Create `src/services/queue_service.py`
- [ ] Implement job enqueuing
- [ ] Implement job dequeuing
- [ ] Implement status updates
- [ ] Implement job retrieval

**Acceptance Criteria:**
- Jobs persist in Redis
- Status updates work correctly
- Jobs retrievable by ID

---

**Task 1.6.2: Deduplication Logic**
```
Priority: 🟡 Important
Estimated: 2 hours
Dependencies: 1.6.1
```

- [ ] Implement file hash computation
- [ ] Implement hash-based duplicate detection
- [ ] Store hash-to-job mapping
- [ ] Handle hash collisions

**Acceptance Criteria:**
- Duplicate files detected
- Hash collisions handled safely
- Mapping persists correctly

---

---

## Phase 2: Integration (Weeks 3-4)

### 2.1 Google Sheets Backup 🔴

**Task 2.1.1: Sheets Service Implementation**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: 1.2.1
```

- [ ] Create `src/services/sheets_service.py`
- [ ] Implement row appending
- [ ] Implement cell updating
- [ ] Handle sheet rotation (monthly)
- [ ] Implement batch operations

**Acceptance Criteria:**
- Rows append correctly
- Updates work correctly
- Monthly sheets created automatically

---

**Task 2.1.2: Audit Trail Logging**
```
Priority: 🔴 Critical
Estimated: 3 hours
Dependencies: 2.1.1
```

- [ ] Log every extraction with full details
- [ ] Log NCB submission status
- [ ] Log exceptions and errors
- [ ] Include timestamps and correlation IDs

**Acceptance Criteria:**
- Complete audit trail in Sheets
- All required columns populated
- Searchable by job/email ID

---

### 2.2 Google Drive Archive 🔴

**Task 2.2.1: Drive Service Implementation**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: 1.2.1
```

- [ ] Create `src/services/drive_service.py`
- [ ] Implement file upload
- [ ] Implement folder creation
- [ ] Organize by date structure
- [ ] Add file metadata

**Acceptance Criteria:**
- Files upload successfully
- Folder structure created automatically
- Metadata attached to files

---

**Task 2.2.2: Attachment Archiving**
```
Priority: 🔴 Critical
Estimated: 2 hours
Dependencies: 2.2.1
```

- [ ] Archive after successful extraction
- [ ] Include email ID in filename
- [ ] Generate shareable URLs
- [ ] Handle large files

**Acceptance Criteria:**
- All processed attachments archived
- Files accessible via URL
- Large files handled correctly

---

### 2.3 Workers Implementation 🔴

**Task 2.3.1: Email Poller Worker**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: 1.4.3, 1.6.1
```

- [ ] Create `src/workers/email_poller.py`
- [ ] Implement polling loop
- [ ] Create jobs for each attachment
- [ ] Handle polling errors
- [ ] Implement graceful shutdown

**Acceptance Criteria:**
- Polls at configured interval
- Creates jobs correctly
- Handles errors without crashing

---

**Task 2.3.2: OCR Processor Worker**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: 1.3.3, 1.6.1, 2.1.2, 2.2.2
```

- [ ] Create `src/workers/ocr_processor.py`
- [ ] Pull jobs from queue
- [ ] Process through OCR
- [ ] Route by confidence
- [ ] Log to Sheets
- [ ] Archive to Drive

**Acceptance Criteria:**
- Processes jobs continuously
- Routes correctly by confidence
- Logs and archives every job

---

**Task 2.3.3: NCB Submitter Worker**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: 1.5.3, 1.6.1
```

- [ ] Create `src/workers/ncb_submitter.py`
- [ ] Pull jobs from submission queue
- [ ] Submit to NCB API
- [ ] Update job status
- [ ] Update Sheets with NCB reference

**Acceptance Criteria:**
- Submits jobs continuously
- Handles NCB unavailability
- Updates all tracking systems

---

### 2.4 Exception Handling 🔴

**Task 2.4.1: Exception Queue**
```
Priority: 🔴 Critical
Estimated: 3 hours
Dependencies: 2.3.2
```

- [ ] Implement exception routing
- [ ] Configure confidence threshold
- [ ] Store exception details
- [ ] Enable exception retrieval

**Acceptance Criteria:**
- Low-confidence jobs routed correctly
- Threshold configurable
- Exceptions retrievable via API

---

**Task 2.4.2: QA Sampling**
```
Priority: 🟡 Important
Estimated: 2 hours
Dependencies: 2.4.1
```

- [ ] Implement random sampling logic
- [ ] Configure sampling percentage
- [ ] Route sampled jobs to review queue

**Acceptance Criteria:**
- Sampling percentage configurable
- Random selection works correctly
- Sampled jobs flagged appropriately

---

### 2.5 Admin Dashboard 🟡

**Task 2.5.1: FastAPI Application Setup**
```
Priority: 🟡 Important
Estimated: 3 hours
Dependencies: 1.1.1
```

- [ ] Create `src/main.py` with FastAPI app
- [ ] Configure CORS
- [ ] Implement API key authentication
- [ ] Add request logging middleware

**Acceptance Criteria:**
- API starts successfully
- Authentication works
- Requests logged

---

**Task 2.5.2: Health Endpoints**
```
Priority: 🟡 Important
Estimated: 2 hours
Dependencies: 2.5.1
```

- [ ] Implement `/health` endpoint
- [ ] Implement `/health/detailed` endpoint
- [ ] Check all component connectivity

**Acceptance Criteria:**
- Health endpoints respond correctly
- Component status accurate
- Latencies measured

---

**Task 2.5.3: Jobs Endpoints**
```
Priority: 🟡 Important
Estimated: 3 hours
Dependencies: 2.5.1, 1.6.1
```

- [ ] Implement `GET /jobs` with filtering
- [ ] Implement `GET /jobs/{id}`
- [ ] Implement `POST /jobs/{id}/retry`

**Acceptance Criteria:**
- Filtering works correctly
- Pagination implemented
- Retry requeues job

---

**Task 2.5.4: Exceptions Endpoints**
```
Priority: 🟡 Important
Estimated: 3 hours
Dependencies: 2.5.1, 2.4.1
```

- [ ] Implement `GET /exceptions`
- [ ] Implement `POST /exceptions/{id}/approve`
- [ ] Implement `POST /exceptions/{id}/reject`

**Acceptance Criteria:**
- Exception list accurate
- Approval triggers submission
- Rejection updates status

---

**Task 2.5.5: Statistics Endpoints**
```
Priority: 🟡 Important
Estimated: 3 hours
Dependencies: 2.5.1, 2.1.2
```

- [ ] Implement `GET /stats/dashboard`
- [ ] Implement `GET /stats/daily`
- [ ] Calculate metrics from data

**Acceptance Criteria:**
- Statistics accurate
- Daily breakdown works
- Performance metrics calculated

---

**Task 2.5.6: Dashboard UI**
```
Priority: 🟢 Nice to have
Estimated: 8 hours
Dependencies: 2.5.2, 2.5.3, 2.5.4, 2.5.5
```

- [ ] Create HTML templates
- [ ] Implement dashboard view
- [ ] Implement exception queue view
- [ ] Implement job log view
- [ ] Add real-time updates (WebSocket)

**Acceptance Criteria:**
- Dashboard displays stats
- Exception queue functional
- Real-time updates work

---

### 2.6 Alerting 🟡

**Task 2.6.1: Alert Service**
```
Priority: 🟡 Important
Estimated: 3 hours
Dependencies: 2.1.1
```

- [ ] Create `src/services/alert_service.py`
- [ ] Implement email alerts
- [ ] Format daily summary
- [ ] Format exception alerts
- [ ] Format system alerts

**Acceptance Criteria:**
- Alerts sent successfully
- Format matches specification
- Recipients configurable

---

---

## Phase 3: Pilot (Weeks 5-6)

### 3.1 Deployment 🔴

**Task 3.1.1: Production Docker Setup**
```
Priority: 🔴 Critical
Estimated: 3 hours
Dependencies: All Phase 1-2 tasks
```

- [ ] Optimize Dockerfile for production
- [ ] Configure resource limits
- [ ] Set up logging aggregation
- [ ] Configure restart policies

**Acceptance Criteria:**
- Container runs stably
- Resources properly constrained
- Logs accessible

---

**Task 3.1.2: Initial Deployment**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: 3.1.1
```

- [ ] Deploy to production server
- [ ] Configure production .env
- [ ] Set up SSL/TLS (if needed)
- [ ] Verify all integrations

**Acceptance Criteria:**
- System running in production
- All integrations working
- No errors in logs

---

### 3.2 Tuning 🔴

**Task 3.2.1: OCR Threshold Tuning**
```
Priority: 🔴 Critical
Estimated: 8 hours (ongoing)
Dependencies: 3.1.2
```

- [ ] Collect sample of real receipts
- [ ] Analyze extraction accuracy
- [ ] Adjust confidence thresholds
- [ ] Document receipt format patterns

**Acceptance Criteria:**
- ≥90% extraction success rate
- ≥95% amount accuracy
- Thresholds documented

---

**Task 3.2.2: Performance Optimization**
```
Priority: 🟡 Important
Estimated: 4 hours
Dependencies: 3.1.2
```

- [ ] Profile OCR processing time
- [ ] Optimize batch processing
- [ ] Tune Redis settings
- [ ] Monitor memory usage

**Acceptance Criteria:**
- <5 minute average processing time
- No memory leaks
- Stable performance under load

---

### 3.3 Monitoring 🟡

**Task 3.3.1: Metrics Collection**
```
Priority: 🟡 Important
Estimated: 4 hours
Dependencies: 3.1.2
```

- [ ] Implement Prometheus metrics
- [ ] Create Grafana dashboards
- [ ] Set up alerting rules

**Acceptance Criteria:**
- Key metrics collected
- Dashboards accessible
- Alerts firing correctly

---

**Task 3.3.2: Log Analysis**
```
Priority: 🟡 Important
Estimated: 3 hours
Dependencies: 3.1.2
```

- [ ] Configure log aggregation
- [ ] Create error tracking
- [ ] Set up log alerts

**Acceptance Criteria:**
- Logs searchable
- Errors tracked
- Anomalies detected

---

---

## Phase 4: Production (Week 7+)

### 4.1 Full Rollout 🔴

**Task 4.1.1: Scale Testing**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: Phase 3 complete
```

- [ ] Test with full claim volume
- [ ] Verify queue handling
- [ ] Check for bottlenecks

**Acceptance Criteria:**
- Handles 200+ claims/day
- No queue backlogs
- Stable performance

---

**Task 4.1.2: Staff Training**
```
Priority: 🔴 Critical
Estimated: 4 hours
Dependencies: 4.1.1
```

- [ ] Create user guide
- [ ] Train claims processors
- [ ] Train operations managers
- [ ] Document exception handling workflow

**Acceptance Criteria:**
- Staff can use dashboard
- Exception workflow understood
- Questions answered

---

### 4.2 Documentation 🟡

**Task 4.2.1: Operations Documentation**
```
Priority: 🟡 Important
Estimated: 4 hours
Dependencies: 4.1.1
```

- [ ] Document deployment process
- [ ] Document troubleshooting steps
- [ ] Create runbook for common issues
- [ ] Document backup/recovery

**Acceptance Criteria:**
- Ops team can manage system
- Issues resolvable with docs
- Recovery procedures tested

---

**Task 4.2.2: API Documentation**
```
Priority: 🟡 Important
Estimated: 2 hours
Dependencies: 2.5.5
```

- [ ] Generate OpenAPI spec
- [ ] Create API usage examples
- [ ] Document authentication

**Acceptance Criteria:**
- OpenAPI spec accurate
- Examples work correctly
- Auth documented

---

### 4.3 Maintenance 🟢

**Task 4.3.1: Ongoing Optimization**
```
Priority: 🟢 Ongoing
Estimated: 2 hours/week
Dependencies: 4.1.1
```

- [ ] Review accuracy metrics weekly
- [ ] Tune OCR for new receipt formats
- [ ] Address edge cases
- [ ] Update documentation

**Acceptance Criteria:**
- Accuracy maintained ≥95%
- New formats supported
- Documentation current

---

---

## Task Dependencies Diagram

```
Phase 1 (Foundation)
├── 1.1 Project Setup
│   ├── 1.1.1 Initialize Project ─────────────────┐
│   ├── 1.1.2 Docker Config ◄─────────────────────┤
│   └── 1.1.3 Configuration ◄─────────────────────┘
├── 1.2 Data Models
│   └── 1.2.1 Pydantic Models ◄── 1.1.3
├── 1.3 OCR Service
│   ├── 1.3.1 PaddleOCR Setup ◄── 1.1.2, 1.2.1
│   ├── 1.3.2 Text Extraction ◄── 1.3.1
│   ├── 1.3.3 Data Structuring ◄── 1.3.2
│   └── 1.3.4 Multi-language ◄── 1.3.3
├── 1.4 Gmail Integration
│   ├── 1.4.1 OAuth Setup ◄── 1.1.3
│   ├── 1.4.2 Email Service ◄── 1.4.1, 1.2.1
│   └── 1.4.3 Processing Logic ◄── 1.4.2
├── 1.5 NCB API
│   ├── 1.5.1 API Discovery (external)
│   ├── 1.5.2 NCB Service ◄── 1.5.1, 1.2.1
│   └── 1.5.3 Error Handling ◄── 1.5.2
└── 1.6 Redis Queue
    ├── 1.6.1 Queue Service ◄── 1.1.2, 1.2.1
    └── 1.6.2 Deduplication ◄── 1.6.1

Phase 2 (Integration)
├── 2.1 Google Sheets
│   ├── 2.1.1 Sheets Service ◄── 1.2.1
│   └── 2.1.2 Audit Trail ◄── 2.1.1
├── 2.2 Google Drive
│   ├── 2.2.1 Drive Service ◄── 1.2.1
│   └── 2.2.2 Archiving ◄── 2.2.1
├── 2.3 Workers
│   ├── 2.3.1 Email Poller ◄── 1.4.3, 1.6.1
│   ├── 2.3.2 OCR Processor ◄── 1.3.3, 1.6.1, 2.1.2, 2.2.2
│   └── 2.3.3 NCB Submitter ◄── 1.5.3, 1.6.1
├── 2.4 Exception Handling
│   ├── 2.4.1 Exception Queue ◄── 2.3.2
│   └── 2.4.2 QA Sampling ◄── 2.4.1
├── 2.5 Admin Dashboard
│   ├── 2.5.1 FastAPI Setup ◄── 1.1.1
│   ├── 2.5.2 Health Endpoints ◄── 2.5.1
│   ├── 2.5.3 Jobs Endpoints ◄── 2.5.1, 1.6.1
│   ├── 2.5.4 Exceptions Endpoints ◄── 2.5.1, 2.4.1
│   ├── 2.5.5 Statistics Endpoints ◄── 2.5.1, 2.1.2
│   └── 2.5.6 Dashboard UI ◄── 2.5.2-5
└── 2.6 Alerting
    └── 2.6.1 Alert Service ◄── 2.1.1

Phase 3 (Pilot)
├── 3.1 Deployment
│   ├── 3.1.1 Production Docker ◄── All Phase 1-2
│   └── 3.1.2 Initial Deployment ◄── 3.1.1
├── 3.2 Tuning
│   ├── 3.2.1 OCR Threshold Tuning ◄── 3.1.2
│   └── 3.2.2 Performance Optimization ◄── 3.1.2
└── 3.3 Monitoring
    ├── 3.3.1 Metrics Collection ◄── 3.1.2
    └── 3.3.2 Log Analysis ◄── 3.1.2

Phase 4 (Production)
├── 4.1 Full Rollout
│   ├── 4.1.1 Scale Testing ◄── Phase 3 complete
│   └── 4.1.2 Staff Training ◄── 4.1.1
├── 4.2 Documentation
│   ├── 4.2.1 Operations Documentation ◄── 4.1.1
│   └── 4.2.2 API Documentation ◄── 2.5.5
└── 4.3 Maintenance
    └── 4.3.1 Ongoing Optimization ◄── 4.1.1
```

---

## Effort Summary

| Phase | Tasks | Critical | Est. Hours |
|-------|-------|----------|------------|
| Phase 1 | 17 | 14 | 56 |
| Phase 2 | 15 | 9 | 52 |
| Phase 3 | 6 | 3 | 26 |
| Phase 4 | 5 | 2 | 16 |
| **Total** | **43** | **28** | **150** |

**Estimated Timeline:** 6-8 weeks with single developer
