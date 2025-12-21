# CLAUDE.md - Instructions for Claude Code

## Project: Claims Data Entry Agent

An internal automation tool for a TPA that extracts claim data from emails and enters it into the NCB core processing system.

## Quick Start Commands

```bash
# Setup
pip install -e ".[dev]"
docker-compose up -d redis

# Run tests
pytest tests/ -v

# Start development server
python -m src.main

# Build production
docker-compose -f docker-compose.prod.yml build
```

## Project Context

This is a **data entry assistant only**. It does NOT:
- Validate claims against policy rules
- Check member eligibility
- Approve or reject claims
- Communicate with members

It DOES:
- Monitor Gmail for claim emails with attachments
- Extract data from receipts using PaddleOCR-VL (0.9B)
- Submit structured data to NCB via API
- Log to Google Sheets, archive to Google Drive
- Route low-confidence extractions to exception queue

## Architecture

```
Email → Poller → Redis Queue → OCR Worker → NCB Submitter → NCB API
                     ↓               ↓              ↓
              (Deduplication)   (Sheets Log)  (Drive Archive)
                                     ↓
                              Exception Queue
```

## Key Files

| File | Purpose |
|------|---------|
| `docs/PRD.md` | Product requirements |
| `docs/TECHNICAL_SPEC.md` | Technical architecture |
| `docs/API_CONTRACTS.md` | API specifications |
| `docs/DEVELOPMENT_TASKS.md` | Task breakdown |
| `PROMPT.md` | AI coder instructions |
| `.cursorrules` | Cursor-specific rules |

## Tech Stack

- **Language:** Python 3.10+
- **API:** FastAPI
- **OCR:** PaddleOCR-VL (0.9B) with GPU
- **Queue:** Redis
- **Container:** Docker with NVIDIA runtime
- **External APIs:** Gmail, Google Sheets, Google Drive, NCB

## Code Standards

1. **Type hints everywhere** - Use Pydantic models
2. **Async I/O** - Use async/await for all I/O
3. **Structured logging** - Use structlog
4. **Error handling** - Never lose data, always log to Sheets

## Directory Structure

```
src/
├── config/settings.py     # Pydantic Settings
├── models/               # Data models
├── services/             # Business logic
├── workers/              # Background workers
├── api/routes/           # API endpoints
└── utils/                # Helpers
```

## Confidence Thresholds

- **≥90%**: Auto-submit to NCB
- **75-89%**: Submit with review flag
- **<75%**: Route to exception queue

## Data Fields to Extract

Required: member_id, member_name, provider_name, service_date, receipt_number, total_amount
Optional: provider_address, itemized_charges, gst_sst_amount

## Malaysian Receipt Notes

- Currency: RM (Malaysian Ringgit)
- Dates: DD/MM/YYYY or DD-MM-YYYY
- Tax: GST (6%, pre-2018) or SST (10%, current)
- Languages: English, Malay, Chinese, Tamil

## Testing

```bash
# All tests
pytest

# With coverage
pytest --cov=src tests/

# Specific test
pytest tests/test_ocr_service.py -v
```

## Common Tasks

### Add a new service
1. Create `src/services/my_service.py`
2. Add config to `src/config/settings.py`
3. Add tests to `tests/test_my_service.py`

### Add an API endpoint
1. Create route in `src/api/routes/`
2. Add to router in `src/api/__init__.py`
3. Update `API_CONTRACTS.md`

### Add a worker
1. Create `src/workers/my_worker.py`
2. Register in main.py startup
3. Update docker-compose.yml if separate process

## Environment Variables

See `.env.example` for all required variables. Key ones:
- `GMAIL_CREDENTIALS_PATH`
- `NCB_API_BASE_URL`, `NCB_API_KEY`
- `SHEETS_SPREADSHEET_ID`
- `DRIVE_FOLDER_ID`
- `REDIS_URL`
- `OCR_USE_GPU`

## Getting Help

1. Check `docs/` for detailed specifications
2. Check `PROMPT.md` for implementation guidelines
3. Search codebase for similar patterns
