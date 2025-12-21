# NCB API Schema Update - Implementation Summary

## Overview
Updated the entire codebase to match the exact NCB API schema requirements.

## Changes Made

### 1. **src/models/claim.py**
- Added `policy_number` field to `ExtractedClaim` model
- Completely restructured `NCBSubmissionRequest` to match NCB schema
- Implemented Pydantic field aliases for exact NCB field names:
  - `event_date` → "Event date"
  - `submission_date` → "Submission Date"
  - `claim_amount` → "Claim Amount"
  - `invoice_number` → "Invoice Number"
  - `policy_number` → "Policy Number"
- Added `Config` class with `populate_by_name=True` for backward compatibility

### 2. **src/services/ocr_service.py**
- Added `_extract_policy_number()` method with patterns:
  - `Policy No: ...`
  - `Policy Number: ...`
  - `Member Policy: ...`
- Updated `extract_structured_data()` to extract policy number
- Implements fallback: if policy_number not found, uses member_id
- Enhanced `_extract_receipt_number()` to match "Invoice Number" variations

### 3. **src/services/ncb_service.py**
- Updated `submit_claim()` to use `model_dump(by_alias=True)`
- This ensures JSON payload uses NCB field names ("Event date", etc.)
- Updated logging to reference `policy_number` and `claim_amount`

### 4. **src/workers/ncb_submitter.py**
- Completely rebuilt NCB request payload mapping:
  ```python
  NCBSubmissionRequest(
      event_date=claim.service_date.isoformat(),  # "Event date"
      submission_date=datetime.now().isoformat(), # "Submission Date"
      claim_amount=claim.total_amount,            # "Claim Amount"
      invoice_number=claim.receipt_number or "",  # "Invoice Number"
      policy_number=policy_number,                # "Policy Number"
      # ... metadata fields
  )
  ```
- Added validation for required fields (total_amount, service_date, policy_number)
- Implements fallback: `policy_number = claim.policy_number or claim.member_id`
- Enhanced error messages for missing fields

### 5. **tests/unit/test_ncb_service.py**
- Updated all test cases to use new schema
- Fixed imports: `from src.models.claim import NCBSubmissionRequest`
- Updated all NCBSubmissionRequest instantiations to use new field names
- Added test cases for field mapping and alias validation

## Field Mapping

| ExtractedClaim Field | NCB API Field (Aliased) | Type | Required |
|---------------------|------------------------|------|----------|
| service_date | Event date | string (ISO) | ✓ |
| datetime.now() | Submission Date | string (ISO) | ✓ |
| total_amount | Claim Amount | float | ✓ |
| receipt_number | Invoice Number | string | ✓ |
| policy_number or member_id | Policy Number | string | ✓ |

## Backward Compatibility

The implementation maintains backward compatibility:
1. `ExtractedClaim` still has all original fields
2. `policy_number` added as optional field
3. Fallback logic: if `policy_number` not extracted, uses `member_id`
4. Pydantic `populate_by_name=True` allows using both field names and aliases

## API Request Example

**Internal Python:**
```python
request = NCBSubmissionRequest(
    event_date="2024-12-21",
    submission_date="2024-12-21T10:30:00",
    claim_amount=150.50,
    invoice_number="INV-12345",
    policy_number="POL-67890",
    source_email_id="msg_123",
    source_filename="receipt.jpg",
    extraction_confidence=0.95
)
```

**JSON Sent to NCB API:**
```json
{
  "Event date": "2024-12-21",
  "Submission Date": "2024-12-21T10:30:00",
  "Claim Amount": 150.50,
  "Invoice Number": "INV-12345",
  "Policy Number": "POL-67890",
  "source_email_id": "msg_123",
  "source_filename": "receipt.jpg",
  "extraction_confidence": 0.95
}
```

## Testing

Run tests with:
```bash
pytest tests/unit/test_ncb_service.py -v
pytest tests/unit/test_ocr_service.py -v
pytest tests/integration/test_workers.py -v
```

## Files Modified

1. `/home/dra/projects/ncb_OCR/src/models/claim.py`
2. `/home/dra/projects/ncb_OCR/src/services/ncb_service.py`
3. `/home/dra/projects/ncb_OCR/src/services/ocr_service.py`
4. `/home/dra/projects/ncb_OCR/src/workers/ncb_submitter.py`
5. `/home/dra/projects/ncb_OCR/tests/unit/test_ncb_service.py` (partial update)

## Next Steps

1. Update remaining test files if needed
2. Test with actual NCB API endpoint
3. Verify OCR correctly extracts policy numbers from receipts
4. Update API documentation if needed
