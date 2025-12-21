# Claims Data Entry Agent

An AI-powered agent that automates the extraction of claim data from emails and enters it into the NCB core processing system.

## Overview

This agent functions as a **data entry assistant only**—it does not perform claims adjudication or processing logic. All claim validation, eligibility checks, and approvals continue to be handled within NCB and by claims processors.

### Key Features

- 📧 **Email Monitoring**: Automatically polls Gmail inbox for claim submissions
- 🔍 **OCR Extraction**: Uses PaddleOCR-VL for accurate multi-language text extraction
- 📊 **NCB Integration**: Submits structured data directly to NCB via API
- 📋 **Audit Trail**: Complete logging to Google Sheets
- 📁 **Document Archive**: Original attachments stored in Google Drive
- ⚠️ **Exception Handling**: Low-confidence extractions routed for manual review

### What This Agent Does NOT Do

- ❌ Validate claims against policy rules or coverage limits
- ❌ Check member eligibility or benefit balances
- ❌ Approve or reject claims
- ❌ Communicate with members
- ❌ Replace claims processors

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| API Framework | FastAPI |
| OCR Engine | PaddleOCR-VL (0.9B) |
| Queue | Redis |
| Container | Docker |
| External APIs | Gmail, Google Sheets, Google Drive, NCB |

## Documentation

| Document | Description |
|----------|-------------|
| [PROMPT.md](./PROMPT.md) | AI coder instructions and project context |
| [CLAUDE.md](./CLAUDE.md) | Claude Code specific instructions |
| [.cursorrules](./.cursorrules) | Cursor IDE AI rules |
| [docs/PRD.md](./docs/PRD.md) | Product Requirements Document |
| [docs/TECHNICAL_SPEC.md](./docs/TECHNICAL_SPEC.md) | Technical Architecture |
| [docs/API_CONTRACTS.md](./docs/API_CONTRACTS.md) | API Specifications |
| [docs/DEVELOPMENT_TASKS.md](./docs/DEVELOPMENT_TASKS.md) | Development Task Breakdown |
| [docs/DOCKER.md](./docs/DOCKER.md) | Docker Deployment Guide |
| [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) | Production Deployment Guide |

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- NVIDIA GPU with CUDA 11.8+
- Google Cloud Project with Gmail, Sheets, Drive APIs enabled
- NCB API access

### Installation

```bash
# Clone repository
git clone <repository-url>
cd ncb_OCR

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e ".[dev]"

# Copy environment configuration
cp .env.example .env
# Edit .env with your configuration
```

### Docker Quick Start

**Development:**
```bash
# Start all services with Docker
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

**Production:**
```bash
# Build and start production services
docker compose -f docker-compose.prod.yml up -d

# Check health
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

For complete Docker setup and troubleshooting, see [docs/DOCKER.md](./docs/DOCKER.md).

### Setup Google APIs

```bash
# Run Gmail OAuth setup
python scripts/setup_gmail.py

# Initialize Google Sheets
python scripts/init_sheets.py
```

### Development

```bash
# Start Redis only
docker compose up -d redis

# Run development server
python -m src.main

# Run tests
pytest tests/ -v
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CLAIMS DATA ENTRY AGENT                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Gmail API ──▶ Email Poller ──▶ Redis Queue ──▶ OCR Worker  │
│                                                      │       │
│                                              ┌───────┘       │
│                                              ▼               │
│  NCB API ◀── NCB Submitter ◀── PaddleOCR-VL (0.9B)         │
│      │              │                                        │
│      │              ▼                                        │
│      │      Google Sheets ──────▶ Google Drive              │
│      │       (Audit Log)          (Archive)                 │
│      │                                                       │
│      ▼                                                       │
│  Exception Queue ◀── Admin Dashboard                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

See [.env.example](./.env.example) for all configuration options.

Key settings:

| Variable | Description |
|----------|-------------|
| `GMAIL_CREDENTIALS_PATH` | Path to Gmail OAuth credentials |
| `NCB_API_BASE_URL` | NCB API endpoint |
| `OCR_HIGH_CONFIDENCE_THRESHOLD` | Threshold for auto-submission (default: 0.90) |
| `OCR_USE_GPU` | Enable GPU acceleration (default: true) |

## Success Metrics

| Metric | Target |
|--------|--------|
| Extraction success rate | ≥90% |
| OCR accuracy (amounts) | ≥95% |
| Email to NCB submission | <5 minutes |
| Data entry time saved | ≥80% |

## Project Status

- [ ] Phase 1: Foundation (Weeks 1-2)
- [ ] Phase 2: Integration (Weeks 3-4)
- [ ] Phase 3: Pilot (Weeks 5-6)
- [ ] Phase 4: Production (Week 7+)

## License

Internal use only.

## Author

Prepared by Armijn Mustapa  
Assisted by Claude.ai
