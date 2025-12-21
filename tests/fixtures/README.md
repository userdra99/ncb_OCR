# Test Fixtures

This directory contains test data and fixtures for the Claims Data Entry Agent test suite.

## Directory Structure

```
fixtures/
├── images/
│   ├── sample_receipt.jpg          # Standard English receipt
│   ├── rotated_receipt.jpg         # Rotated image test
│   ├── complete_receipt.jpg        # All fields present
│   ├── malay_receipt.jpg           # Malay language receipt
│   ├── chinese_receipt.jpg         # Chinese characters
│   ├── unclear_receipt.jpg         # Low quality / unclear
│   └── sample_receipt.pdf          # PDF format test
├── emails/
│   ├── single_attachment.json      # Email metadata with 1 attachment
│   ├── multiple_attachments.json   # Email with 3 attachments
│   └── no_attachments.json         # Email without attachments
└── expected/
    ├── english_extraction.json     # Expected extraction from English receipt
    ├── malay_extraction.json       # Expected extraction from Malay receipt
    └── itemized_extraction.json    # Expected itemized charges
```

## Creating Test Fixtures

### Sample Receipt Images

You can create test receipt images using the provided templates or use actual (anonymized) receipts.

**Required test cases:**
1. **High confidence (>90%)**: Clear, well-lit, straight receipt with all fields
2. **Medium confidence (75-89%)**: Slightly unclear or rotated receipt
3. **Low confidence (<75%)**: Poor quality, handwritten, or incomplete receipt

### Malaysian Receipt Formats

Test receipts should cover:
- **Languages**: English, Malay, Chinese, Tamil
- **Currency formats**: RM 150.00, RM150.00, 150.00 MYR
- **Date formats**: DD/MM/YYYY, DD-MM-YYYY, D/M/YYYY
- **Tax types**: GST (6%, pre-2018), SST (6-10%, current)

### Email Fixtures

Email metadata JSON files should match Gmail API format:

```json
{
  "id": "msg_abc123",
  "payload": {
    "headers": [
      {"name": "From", "value": "john.doe@client.com"},
      {"name": "Subject", "value": "Medical Claim - December 2024"},
      {"name": "Date", "value": "Wed, 18 Dec 2024 10:42:00 +0800"}
    ],
    "parts": [
      {
        "filename": "receipt_001.jpg",
        "body": {
          "attachmentId": "att_abc123",
          "size": 245678
        }
      }
    ]
  }
}
```

## Usage in Tests

```python
import pytest
from pathlib import Path

@pytest.fixture
def test_data_dir() -> Path:
    return Path(__file__).parent / "fixtures"

def test_ocr_extraction(test_data_dir):
    receipt_path = test_data_dir / "images" / "sample_receipt.jpg"
    # Test OCR on sample receipt
```

## Generating Fixtures

Run this script to generate synthetic test data:

```bash
python tests/fixtures/generate_fixtures.py
```

## Privacy & Security

- **DO NOT** include real member data or actual receipts with PHI
- Use anonymized or synthetic data only
- Receipt images should have:
  - Fictional names (e.g., "John Doe", "Ahmad bin Ali")
  - Test member IDs (e.g., "M12345")
  - Fictional clinic names
  - Reasonable but fake amounts

## Adding New Fixtures

When adding new test fixtures:

1. Name files descriptively: `{language}_{quality}_{feature}.jpg`
2. Create corresponding expected output in `expected/`
3. Document any special characteristics
4. Update this README

## Maintenance

Test fixtures should be reviewed and updated:
- When OCR model is updated
- When new Malaysian receipt formats are encountered
- When edge cases are discovered in production
