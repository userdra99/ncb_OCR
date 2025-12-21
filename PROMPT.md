# Claims Data Entry Agent - AI Coder Instructions

You are building a **Claims Data Entry Agent** - an internal automation tool for a Third Party Administrator (TPA) that extracts claim data from emails and enters it into the NCB core processing system.

## Project Context

This agent automates data entry ONLY. It does NOT:
- Validate claims against policy rules
- Check member eligibility
- Approve or reject claims
- Communicate with members
- Replace claims processors

It DOES:
- Monitor Gmail inbox for claim emails with attachments
- Extract data from receipts/invoices using PaddleOCR-VL
- Submit structured data to NCB via API
- Maintain audit trails in Google Sheets
- Archive attachments to Google Drive
- Flag low-confidence extractions for human review

## Tech Stack (Mandatory)

| Component | Technology |
|-----------|------------|
| OCR Engine | PaddleOCR-VL (0.9B) - Apache 2.0 license |
| Runtime | Python 3.10+ |
| Queue | Redis |
| Web Framework | FastAPI |
| Containerization | Docker + Docker Compose |
| Email | Gmail API |
| Storage | Google Sheets API, Google Drive API |
| Core System | NCB API (internal) |
| Orchestration | MCP (Model Context Protocol) |

## Hardware Requirements

- GPU: NVIDIA RTX 2060 (6GB) minimum; RTX 3060/4060 recommended
- CUDA: 11.8+
- RAM: 16GB minimum; 32GB recommended
- Storage: 50GB SSD

## Project Structure

```
claims-data-entry-agent/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── src/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py            # Pydantic settings
│   ├── services/
│   │   ├── __init__.py
│   │   ├── email_service.py       # Gmail API integration
│   │   ├── ocr_service.py         # PaddleOCR-VL wrapper
│   │   ├── ncb_service.py         # NCB API client
│   │   ├── sheets_service.py      # Google Sheets backup
│   │   ├── drive_service.py       # Google Drive archive
│   │   └── queue_service.py       # Redis job queue
│   ├── models/
│   │   ├── __init__.py
│   │   ├── claim.py               # Claim data models
│   │   ├── extraction.py          # OCR extraction models
│   │   └── job.py                 # Job/task models
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── email_poller.py        # Inbox monitoring worker
│   │   ├── ocr_processor.py       # OCR extraction worker
│   │   └── ncb_submitter.py       # NCB submission worker
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py          # Health check endpoints
│   │   │   ├── jobs.py            # Job management endpoints
│   │   │   └── exceptions.py      # Exception queue endpoints
│   │   └── dependencies.py
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       ├── deduplication.py       # Hash-based duplicate detection
│       └── confidence.py          # OCR confidence scoring
├── admin-ui/
│   ├── templates/
│   └── static/
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_ocr_service.py
│   ├── test_email_service.py
│   └── test_ncb_service.py
├── scripts/
│   ├── setup_gmail.py            # Gmail OAuth setup
│   └── init_sheets.py            # Initialize Google Sheets
├── docs/
│   ├── PRD.md
│   ├── TECHNICAL_SPEC.md
│   ├── API_CONTRACTS.md
│   └── DEVELOPMENT_TASKS.md
├── .env.example
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Development Guidelines

### Code Style
- Use type hints everywhere
- Pydantic models for all data structures
- Async/await for I/O operations
- Comprehensive error handling with custom exceptions
- Structured logging with correlation IDs

### OCR Integration
```python
# PaddleOCR-VL initialization pattern
from paddleocr import PaddleOCR

ocr = PaddleOCR(
    use_angle_cls=True,
    lang='en',  # Supports: en, ch, ms, ta (109 languages)
    use_gpu=True,
    show_log=False
)
```

### Confidence Thresholds
- **High confidence (≥90%)**: Auto-submit to NCB
- **Medium confidence (75-89%)**: Submit with review flag
- **Low confidence (<75%)**: Route to exception queue

### Data Fields to Extract
1. Member ID
2. Member name
3. Provider/clinic name
4. Provider address
5. Date of service
6. Receipt number
7. Total amount
8. Itemized charges (if available)
9. GST/SST amounts
10. Email timestamp
11. Attachment filenames

### Error Handling Priority
1. Never lose data - always log to Sheets if NCB fails
2. Retry transient failures with exponential backoff
3. Alert on persistent failures
4. Maintain complete audit trail

### Security Requirements
- All processing on-premise (no external AI services)
- PDPA compliance for medical data
- Credentials in environment variables only
- No PHI in logs

## Key Integration Points

### Gmail API
- Poll interval: 30 seconds
- Filter: Has attachments, unread
- Mark as read after processing
- Label processed emails

### NCB API
- POST /claims/submit
- Retry on 5xx errors
- Queue on connection failure
- Capture claim reference number

### Google Sheets
- One row per extraction
- Columns: timestamp, email_id, ocr_output, ncb_status, ncb_ref
- Daily sheet rotation

### Google Drive
- Folder structure: /claims/{YYYY}/{MM}/{DD}/
- Original filename preserved
- Metadata: email_id, processing_timestamp

## Testing Requirements

- Unit tests for all services
- Integration tests for API endpoints
- Mock external services in tests
- Test Malaysian receipt formats specifically
- Test multi-language extraction (EN, MS, ZH, TA)

## Success Metrics to Track

| Metric | Target |
|--------|--------|
| Extraction success rate | ≥90% |
| OCR accuracy (amounts) | ≥95% |
| Email to NCB submission | <5 minutes |
| NCB API success rate | ≥99% |

## Commands Reference

```bash
# Development
docker-compose up -d
python -m pytest tests/
python src/main.py

# Production
docker-compose -f docker-compose.prod.yml up -d
```

## When Implementing

1. Start with core OCR service and test with sample Malaysian receipts
2. Add Gmail integration with proper OAuth flow
3. Implement NCB API client (schema TBD - requires discovery session)
4. Add Google Sheets/Drive backup layer
5. Build admin dashboard last
6. Always maintain backward compatibility
