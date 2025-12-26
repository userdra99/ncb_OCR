# Enhanced Email Subject/Body Extraction - Technical Architecture Design

**Version:** 1.0
**Date:** 2025-12-26
**Author:** System Architect (Hive Mind Swarm)
**Status:** Design Phase

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Component Design](#component-design)
4. [Data Models](#data-models)
5. [Integration Points](#integration-points)
6. [Implementation Plan](#implementation-plan)
7. [Testing Strategy](#testing-strategy)
8. [Configuration](#configuration)
9. [Error Handling](#error-handling)
10. [Performance Considerations](#performance-considerations)

---

## 1. Executive Summary

This document outlines the technical architecture for enhancing the Claims Data Entry Agent with intelligent email subject/body text extraction capabilities. The enhancement will enable extraction of claim data directly from email content (subject lines and body text) in addition to the existing receipt OCR functionality.

### Goals

- Extract claim fields from email subject lines and body text
- Reduce dependency on OCR-only processing
- Improve extraction confidence through multi-source data fusion
- Maintain backward compatibility with existing OCR pipeline
- Handle Malaysian healthcare claim email patterns

### Key Benefits

- **Faster processing**: Email text extraction is instant vs OCR processing time
- **Higher confidence**: Cross-validation between email content and OCR
- **Better UX**: Pre-populate known fields before OCR completes
- **Reduced exceptions**: Extract member ID, dates, amounts from emails directly

---

## 2. Architecture Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       EMAIL POLLER WORKER                            │
│                                                                      │
│  ┌────────────┐    ┌──────────────────┐    ┌─────────────────┐    │
│  │   Gmail    │───▶│  Email Parser    │───▶│  Job Creation   │    │
│  │   Inbox    │    │  (NEW)           │    │                 │    │
│  └────────────┘    └──────────────────┘    └─────────────────┘    │
│                           │                          │              │
│                           │                          │              │
│                           ▼                          ▼              │
│                    ┌──────────────┐         ┌──────────────┐       │
│                    │ EmailContent │         │ Job w/ Email │       │
│                    │    Model     │         │  Extraction  │       │
│                    └──────────────┘         └──────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ Redis Queue
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     OCR PROCESSOR WORKER                             │
│                                                                      │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐     │
│  │ Email Data   │    │   OCR Service    │    │ Data Fusion  │     │
│  │ (from Job)   │───▶│   (Existing)     │───▶│   Engine     │     │
│  └──────────────┘    └──────────────────┘    │   (NEW)      │     │
│                                               └──────────────┘     │
│                                                       │             │
│                                                       ▼             │
│                                               ┌──────────────┐     │
│                                               │ Merged Claim │     │
│                                               │   w/ Scores  │     │
│                                               └──────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ Redis Queue
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      NCB SUBMITTER WORKER                            │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌─────────────────┐      │
│  │ Final Claim  │───▶│ NCB Service  │───▶│ Sheets/Drive    │      │
│  │ (Merged)     │    │ (Existing)   │    │ (Existing)      │      │
│  └──────────────┘    └──────────────┘    └─────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
1. Email arrives with subject: "Claim for member ABC123 - RM150.00"
   └─▶ EmailParser extracts: member_id="ABC123", amount=150.00

2. Email body contains: "Patient: John Doe, Service Date: 15/12/2024"
   └─▶ EmailParser extracts: member_name="John Doe", date=2024-12-15

3. Job created with EmailExtraction data (confidence scores per field)
   └─▶ Enqueued to OCR queue

4. OCR processes receipt image
   └─▶ Extracts: member_id="ABC123", amount=150.00, provider="Klinik Health"

5. DataFusionEngine merges both sources
   └─▶ member_id: Confidence 0.95 (both agree)
   └─▶ amount: Confidence 0.95 (both agree)
   └─▶ member_name: Confidence 0.80 (only from email)
   └─▶ provider: Confidence 0.85 (only from OCR)

6. Merged claim submitted to NCB
```

---

## 3. Component Design

### 3.1 EmailContentParser (NEW)

**Location:** `src/services/email_parser.py`

**Responsibility:** Parse email subject and body to extract claim fields

**Key Methods:**

```python
class EmailContentParser:
    """Parse email subject and body to extract claim data."""

    async def parse_email(
        self,
        subject: str,
        body: str,
        headers: dict
    ) -> EmailExtractionResult:
        """
        Parse email content and extract claim fields.

        Returns:
            EmailExtractionResult with extracted fields and confidence
        """

    def _parse_subject_line(self, subject: str) -> dict:
        """Extract fields from subject line using patterns."""

    def _parse_body_text(self, body: str) -> dict:
        """Extract fields from email body."""

    def _parse_html_body(self, html: str) -> dict:
        """Parse HTML email body (convert to text first)."""

    def _extract_member_id(self, text: str) -> tuple[str | None, float]:
        """Extract member ID with confidence score."""

    def _extract_amount(self, text: str) -> tuple[float | None, float]:
        """Extract amount with confidence score."""

    def _extract_date(self, text: str) -> tuple[datetime | None, float]:
        """Extract service date with confidence score."""

    def _extract_member_name(self, text: str) -> tuple[str | None, float]:
        """Extract member/patient name with confidence score."""

    def _calculate_field_confidence(
        self,
        field_value: Any,
        extraction_method: str,
        validation_passed: bool
    ) -> float:
        """Calculate confidence score for extracted field."""
```

**Pattern Matching:**

```python
# Subject line patterns (Malaysian healthcare)
SUBJECT_PATTERNS = {
    'member_id': [
        r'Member[:\s]+([A-Z0-9]+)',
        r'Member\s*ID[:\s]+([A-Z0-9]+)',
        r'Policy[:\s]+([A-Z0-9]+)',
        r'IC[:\s]+(\d{6}-\d{2}-\d{4})',  # Malaysian IC
    ],
    'amount': [
        r'RM\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        r'Amount[:\s]+RM\s*(\d+\.\d{2})',
        r'Total[:\s]+RM\s*(\d+\.\d{2})',
    ],
    'claim_type': [
        r'(Outpatient|Inpatient|Dental|Optical)',
        r'(Klinik|Hospital|Pharmacy)',
    ],
    'provider_name': [
        r'(?:at|from|@)\s+([A-Z][A-Za-z\s&.,\'-]+(?:Clinic|Hospital|Klinik))',
    ],
}

# Body text patterns
BODY_PATTERNS = {
    'member_name': [
        r'Patient\s*Name[:\s]+([A-Z][A-Za-z\s.\',-]+)',
        r'Member\s*Name[:\s]+([A-Z][A-Za-z\s.\',-]+)',
        r'Name[:\s]+([A-Z][A-Za-z\s.\',-]+)',
    ],
    'service_date': [
        r'(?:Date|Service\s*Date|Visit\s*Date)[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{4})',
        r'(?:On|Date)[:\s]+(\d{1,2}\s+(?:Jan|Feb|Mac|Apr|Mei|Jun|Jul|Ogos|Sep|Okt|Nov|Dis)\s+\d{4})',
    ],
    'receipt_number': [
        r'(?:Receipt|Invoice)\s*(?:No|Number)[:\s]+([A-Z0-9-]+)',
        r'Reference[:\s]+([A-Z0-9-]+)',
    ],
    'provider_address': [
        r'(?:Address|Location)[:\s]+(.+?)(?:\n|$)',
    ],
}
```

### 3.2 DataFusionEngine (NEW)

**Location:** `src/services/data_fusion.py`

**Responsibility:** Merge email extraction and OCR extraction with intelligent conflict resolution

**Key Methods:**

```python
class DataFusionEngine:
    """Merge data from multiple extraction sources."""

    async def merge_extractions(
        self,
        email_extraction: EmailExtractionResult | None,
        ocr_extraction: ExtractionResult,
    ) -> FusedExtractionResult:
        """
        Merge email and OCR extractions with conflict resolution.

        Strategy:
        - If both sources agree: boost confidence
        - If sources differ: use higher confidence source
        - If only one source: use that source with original confidence
        """

    def _merge_field(
        self,
        field_name: str,
        email_value: Any,
        email_confidence: float,
        ocr_value: Any,
        ocr_confidence: float,
    ) -> tuple[Any, float, str]:
        """
        Merge single field from both sources.

        Returns:
            (merged_value, final_confidence, source_indicator)
        """

    def _values_match(
        self,
        field_name: str,
        value1: Any,
        value2: Any
    ) -> bool:
        """Check if two values match (with fuzzy matching for strings)."""

    def _boost_confidence(
        self,
        confidence1: float,
        confidence2: float
    ) -> float:
        """Boost confidence when both sources agree."""

    def _resolve_conflict(
        self,
        field_name: str,
        email_value: Any,
        email_conf: float,
        ocr_value: Any,
        ocr_conf: float,
    ) -> tuple[Any, float, str]:
        """Resolve conflicts between sources."""
```

**Conflict Resolution Strategy:**

```python
CONFLICT_RESOLUTION = {
    # Field-specific rules
    'member_id': 'prefer_higher_confidence',  # Critical field
    'member_name': 'prefer_ocr',  # Better from receipt
    'provider_name': 'prefer_ocr',  # Better from receipt
    'service_date': 'prefer_email',  # More reliable in email
    'total_amount': 'prefer_higher_confidence',  # Critical field
    'receipt_number': 'prefer_ocr',  # Always from receipt

    # Default strategy
    'default': 'prefer_higher_confidence',
}

CONFIDENCE_BOOST = {
    # When both sources agree, boost by:
    'exact_match': 0.10,  # +10% for exact match
    'fuzzy_match': 0.05,  # +5% for fuzzy match (strings)
    'max_confidence': 0.98,  # Cap at 98%
}
```

### 3.3 EmailTextExtractor (NEW)

**Location:** `src/utils/email_text_extractor.py`

**Responsibility:** Extract and clean text from different email formats

**Key Methods:**

```python
class EmailTextExtractor:
    """Extract clean text from various email formats."""

    def extract_plain_text(self, payload: dict) -> str:
        """Extract plain text from email payload."""

    def extract_html_text(self, payload: dict) -> str:
        """Extract and convert HTML to plain text."""

    def extract_multipart_text(self, payload: dict) -> str:
        """Handle multipart emails (plain + HTML)."""

    def clean_text(self, text: str) -> str:
        """
        Clean extracted text:
        - Remove excessive whitespace
        - Normalize line breaks
        - Remove email signatures
        - Remove quoted text (replies)
        - Preserve Malaysian characters (Malay, Chinese, Tamil)
        """

    def extract_forwarded_content(self, text: str) -> str:
        """Extract content from forwarded emails."""
```

---

## 4. Data Models

### 4.1 EmailExtractionResult (NEW)

**Location:** `src/models/email_extraction.py`

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EmailFieldExtraction(BaseModel):
    """Single field extraction from email."""

    value: Any  # Extracted value
    confidence: float = Field(ge=0.0, le=1.0)  # Confidence score
    source: str  # 'subject' or 'body' or 'headers'
    pattern_matched: str | None = None  # Which pattern matched


class EmailExtractionResult(BaseModel):
    """Result of email content parsing."""

    # Extracted fields (each with confidence)
    member_id: EmailFieldExtraction | None = None
    member_name: EmailFieldExtraction | None = None
    policy_number: EmailFieldExtraction | None = None
    provider_name: EmailFieldExtraction | None = None
    service_date: EmailFieldExtraction | None = None
    total_amount: EmailFieldExtraction | None = None
    receipt_number: EmailFieldExtraction | None = None
    claim_type: EmailFieldExtraction | None = None

    # Overall metrics
    overall_confidence: float = Field(ge=0.0, le=1.0)
    fields_extracted: int = 0
    extraction_method: str = "email_parsing"

    # Raw data
    raw_subject: str = ""
    raw_body: str = ""

    # Warnings
    warnings: list[str] = Field(default_factory=list)


class FusedExtractionResult(BaseModel):
    """Result of merging email + OCR extractions."""

    claim: ExtractedClaim  # Final merged claim
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel

    # Field-level tracking
    field_sources: dict[str, str] = {}  # field_name -> 'email'|'ocr'|'both'
    field_confidences: dict[str, float] = {}

    # Source results
    email_extraction: EmailExtractionResult | None = None
    ocr_extraction: ExtractionResult | None = None

    # Conflicts and resolutions
    conflicts: list[dict] = Field(default_factory=list)
    # Example: [{"field": "member_id", "email_value": "ABC",
    #            "ocr_value": "ABD", "resolution": "ocr", "reason": "higher_confidence"}]

    warnings: list[str] = Field(default_factory=list)
```

### 4.2 Enhanced Job Model

**Location:** `src/models/job.py` (modify existing)

```python
class Job(BaseModel):
    """Processing job (ENHANCED)."""

    # ... existing fields ...

    # NEW: Email extraction results
    email_extraction: EmailExtractionResult | None = None
    email_extraction_timestamp: datetime | None = None

    # NEW: Fusion metadata
    data_sources: list[str] = Field(default_factory=list)  # ['email', 'ocr']
    fusion_conflicts: list[dict] = Field(default_factory=list)
```

### 4.3 Enhanced EmailMetadata Model

**Location:** `src/models/email.py` (modify existing)

```python
class EmailMetadata(BaseModel):
    """Email metadata from Gmail (ENHANCED)."""

    # ... existing fields ...

    # NEW: Add body text
    body_text: str = ""  # Plain text body
    body_html: str = ""  # HTML body (if present)
```

---

## 5. Integration Points

### 5.1 Gmail Service Integration

**File:** `src/services/email_service.py`

**Changes Required:**

```python
class EmailService:
    # NEW: Fetch full message body when polling
    async def poll_inbox(self) -> list[EmailMetadata]:
        """
        Poll inbox - NOW INCLUDES BODY TEXT

        Changes:
        - Fetch format='full' instead of 'metadata'
        - Extract body text using EmailTextExtractor
        - Add body_text to EmailMetadata
        """

    # EXISTING: Keep this method, enhance to get body
    async def get_message_body(self, message_id: str) -> str:
        """Enhanced to handle HTML and multipart."""
```

**Implementation Notes:**
- Use batch requests to minimize API calls
- Cache email bodies in Redis (1 hour TTL)
- Handle rate limits with exponential backoff

### 5.2 Email Poller Worker Integration

**File:** `src/workers/email_poller.py`

**Changes Required:**

```python
class EmailPollerWorker:
    def __init__(self):
        # ... existing ...
        self.email_parser = EmailContentParser()  # NEW

    async def _process_email(self, email: EmailMetadata) -> None:
        """
        Process email - NOW PARSES CONTENT

        NEW Steps:
        1. Parse email subject + body
        2. Extract claim fields
        3. Add email_extraction to Job
        4. Enqueue job with email data
        """

        # NEW: Parse email content
        email_extraction = await self.email_parser.parse_email(
            subject=email.subject,
            body=email.body_text,
            headers={},
        )

        # Create job with email extraction
        job = Job(
            # ... existing fields ...
            email_extraction=email_extraction,  # NEW
            data_sources=['email'],  # NEW
        )
```

### 5.3 OCR Processor Worker Integration

**File:** `src/workers/ocr_processor.py`

**Changes Required:**

```python
class OCRProcessorWorker:
    def __init__(self):
        # ... existing ...
        self.fusion_engine = DataFusionEngine()  # NEW

    async def _process_job(self, job: Job) -> None:
        """
        Process job - NOW MERGES EMAIL + OCR

        NEW Steps:
        1. Run OCR (existing)
        2. Merge with email_extraction (NEW)
        3. Calculate fused confidence
        4. Route based on fused confidence
        """

        # Run OCR extraction (existing)
        ocr_result = await self.ocr_service.extract_structured_data(image_path)

        # NEW: Merge with email extraction
        if job.email_extraction:
            fused_result = await self.fusion_engine.merge_extractions(
                email_extraction=job.email_extraction,
                ocr_extraction=ocr_result,
            )

            # Update job with fused result
            await self.queue_service.update_job_status(
                job.id,
                JobStatus.EXTRACTED,
                extraction_result=fused_result,  # Use fused instead of OCR-only
            )
        else:
            # Fallback: OCR-only (backward compatible)
            # ... existing code ...
```

### 5.4 NCB Service Integration

**File:** `src/services/ncb_service.py`

**No changes required** - NCB service consumes final `ExtractedClaim` which is produced by fusion engine.

### 5.5 Sheets Logging Integration

**File:** `src/services/sheets_service.py`

**Changes Required:**

```python
class SheetsService:
    async def log_extraction(
        self,
        job: Job,
        extraction_result: ExtractionResult | FusedExtractionResult
    ) -> str:
        """
        Log to Sheets - NOW LOGS DATA SOURCES

        NEW Columns:
        - Data Sources (email, ocr, both)
        - Email Confidence
        - OCR Confidence
        - Final Confidence
        - Conflicts (JSON)
        """
```

---

## 6. Implementation Plan

### Phase 1: Core Email Parsing (Week 1)

**Tasks:**
1. Create `EmailTextExtractor` utility
   - Plain text extraction
   - HTML to text conversion
   - Text cleaning

2. Create `EmailContentParser` service
   - Subject line parsing
   - Body text parsing
   - Pattern matching
   - Confidence scoring

3. Add data models
   - `EmailFieldExtraction`
   - `EmailExtractionResult`

4. Unit tests for email parsing
   - Test all patterns
   - Test Malaysian formats
   - Test multilingual content

**Deliverables:**
- `src/utils/email_text_extractor.py`
- `src/services/email_parser.py`
- `src/models/email_extraction.py`
- `tests/test_email_parser.py`

### Phase 2: Data Fusion Engine (Week 2)

**Tasks:**
1. Create `DataFusionEngine` service
   - Field merging logic
   - Conflict resolution
   - Confidence boosting

2. Add fused data model
   - `FusedExtractionResult`

3. Enhance Job model
   - Add email_extraction field
   - Add fusion metadata

4. Unit tests for fusion
   - Test agreement scenarios
   - Test conflict resolution
   - Test confidence calculations

**Deliverables:**
- `src/services/data_fusion.py`
- Enhanced `src/models/job.py`
- Enhanced `src/models/extraction.py`
- `tests/test_data_fusion.py`

### Phase 3: Gmail Service Enhancement (Week 2)

**Tasks:**
1. Enhance `EmailService`
   - Fetch full message bodies
   - Add body text to metadata
   - Implement caching

2. Enhance `EmailMetadata` model
   - Add body_text field
   - Add body_html field

3. Update email poller worker
   - Integrate EmailContentParser
   - Add email extraction to jobs

4. Integration tests

**Deliverables:**
- Enhanced `src/services/email_service.py`
- Enhanced `src/models/email.py`
- Enhanced `src/workers/email_poller.py`
- `tests/test_email_service_enhanced.py`

### Phase 4: OCR Worker Enhancement (Week 3)

**Tasks:**
1. Integrate DataFusionEngine into OCR worker
   - Merge email + OCR
   - Route based on fused confidence
   - Handle backward compatibility

2. Enhance Sheets logging
   - Add data source columns
   - Log fusion metadata

3. Integration tests
   - Test full pipeline
   - Test email-only jobs
   - Test OCR-only jobs (no email data)
   - Test fused jobs

**Deliverables:**
- Enhanced `src/workers/ocr_processor.py`
- Enhanced `src/services/sheets_service.py`
- `tests/test_pipeline_integration.py`

### Phase 5: Configuration & Documentation (Week 3)

**Tasks:**
1. Add configuration options
   - Email parsing thresholds
   - Fusion strategies
   - Feature flags

2. Update documentation
   - API contracts
   - Technical spec
   - Operator manual

3. Performance testing
   - Benchmark email parsing
   - Benchmark fusion
   - Monitor memory usage

**Deliverables:**
- Enhanced `src/config/settings.py`
- Updated `docs/API_CONTRACTS.md`
- Updated `docs/TECHNICAL_SPEC.md`
- Performance benchmark report

### Phase 6: Production Rollout (Week 4)

**Tasks:**
1. Feature flag rollout
   - 10% traffic
   - 50% traffic
   - 100% traffic

2. Monitoring and metrics
   - Email extraction success rate
   - Fusion conflict rate
   - Confidence improvements

3. Bug fixes and optimization
   - Handle edge cases
   - Tune confidence thresholds
   - Optimize patterns

**Deliverables:**
- Production deployment
- Monitoring dashboards
- Post-deployment report

---

## 7. Testing Strategy

### 7.1 Unit Tests

```python
# tests/test_email_parser.py
class TestEmailContentParser:
    def test_parse_subject_with_member_id(self):
        """Test extraction of member ID from subject."""

    def test_parse_subject_with_amount(self):
        """Test extraction of amount from subject."""

    def test_parse_body_with_multiple_fields(self):
        """Test extraction of multiple fields from body."""

    def test_malaysian_ic_format(self):
        """Test Malaysian IC number extraction."""

    def test_multilingual_content(self):
        """Test Malay, Chinese, Tamil content."""

    def test_html_email_parsing(self):
        """Test HTML email body parsing."""

# tests/test_data_fusion.py
class TestDataFusionEngine:
    def test_merge_matching_fields(self):
        """Test confidence boost when fields match."""

    def test_resolve_conflict_higher_confidence(self):
        """Test conflict resolution based on confidence."""

    def test_merge_partial_data(self):
        """Test merging when only one source has data."""

    def test_fuzzy_string_matching(self):
        """Test fuzzy matching for names."""
```

### 7.2 Integration Tests

```python
# tests/test_pipeline_integration.py
class TestEnhancedPipeline:
    async def test_email_only_extraction(self):
        """Test extraction from email without attachments."""

    async def test_ocr_only_extraction(self):
        """Test backward compatibility (no email data)."""

    async def test_fused_extraction(self):
        """Test full pipeline with email + OCR fusion."""

    async def test_conflict_resolution(self):
        """Test handling of conflicting data."""

    async def test_confidence_thresholds(self):
        """Test routing based on fused confidence."""
```

### 7.3 Test Data

**Sample Emails:**

```
Subject: Claim for member ABC123 - RM150.00 at Klinik Kesihatan

Body:
Dear TPA,

Please process claim for:
- Patient Name: Ahmad bin Abdullah
- Member ID: ABC123
- Service Date: 15/12/2024
- Provider: Klinik Kesihatan Setiawangsa
- Amount: RM150.00
- Receipt attached

Thanks
```

```
Subject: Medical claim - John Doe (Policy: XYZ789)

Body (HTML):
<p>Member: John Doe</p>
<p>Policy Number: XYZ789</p>
<p>Visit Date: 20-Dec-2024</p>
<p>Hospital: Hospital Pantai</p>
<p>Total: RM850.50</p>
<p>Invoice #: INV-2024-12345</p>
```

---

## 8. Configuration

### 8.1 New Settings

**File:** `src/config/settings.py`

```python
class EmailParsingConfig(BaseSettings):
    """Email parsing configuration."""

    enabled: bool = Field(default=True, alias="EMAIL_PARSING_ENABLED")

    # Confidence thresholds
    min_field_confidence: float = Field(default=0.60, alias="EMAIL_MIN_CONFIDENCE")
    high_confidence_threshold: float = Field(default=0.85, alias="EMAIL_HIGH_CONFIDENCE")

    # Pattern matching
    member_id_patterns: list[str] = Field(
        default=[
            r'Member[:\s]+([A-Z0-9]+)',
            r'Member\s*ID[:\s]+([A-Z0-9]+)',
            r'Policy[:\s]+([A-Z0-9]+)',
        ]
    )

    # Text cleaning
    max_body_length: int = Field(default=10000, alias="EMAIL_MAX_BODY_LENGTH")
    remove_signatures: bool = Field(default=True)
    remove_quoted_text: bool = Field(default=True)


class FusionConfig(BaseSettings):
    """Data fusion configuration."""

    enabled: bool = Field(default=True, alias="FUSION_ENABLED")

    # Conflict resolution
    default_strategy: str = Field(
        default="prefer_higher_confidence",
        alias="FUSION_DEFAULT_STRATEGY"
    )

    # Confidence boosting
    exact_match_boost: float = Field(default=0.10, alias="FUSION_EXACT_BOOST")
    fuzzy_match_boost: float = Field(default=0.05, alias="FUSION_FUZZY_BOOST")
    max_confidence: float = Field(default=0.98, alias="FUSION_MAX_CONFIDENCE")

    # Fuzzy matching
    fuzzy_match_threshold: float = Field(
        default=0.85,
        alias="FUSION_FUZZY_THRESHOLD"
    )  # 85% similarity for fuzzy match


class Settings(BaseSettings):
    # ... existing ...
    email_parsing: EmailParsingConfig = Field(default_factory=EmailParsingConfig)
    fusion: FusionConfig = Field(default_factory=FusionConfig)
```

### 8.2 Environment Variables

```bash
# Email Parsing
EMAIL_PARSING_ENABLED=true
EMAIL_MIN_CONFIDENCE=0.60
EMAIL_HIGH_CONFIDENCE=0.85
EMAIL_MAX_BODY_LENGTH=10000

# Data Fusion
FUSION_ENABLED=true
FUSION_DEFAULT_STRATEGY=prefer_higher_confidence
FUSION_EXACT_BOOST=0.10
FUSION_FUZZY_BOOST=0.05
FUSION_MAX_CONFIDENCE=0.98
FUSION_FUZZY_THRESHOLD=0.85
```

---

## 9. Error Handling

### 9.1 Email Parsing Errors

```python
class EmailParsingError(Exception):
    """Base exception for email parsing."""
    pass

class EmailBodyExtractionError(EmailParsingError):
    """Failed to extract email body text."""
    pass

class PatternMatchError(EmailParsingError):
    """Pattern matching failed."""
    pass

# Graceful degradation
async def parse_email(subject: str, body: str) -> EmailExtractionResult:
    try:
        result = EmailExtractionResult()

        try:
            # Parse subject
            subject_fields = self._parse_subject_line(subject)
            result.update(subject_fields)
        except Exception as e:
            logger.warning("Subject parsing failed", error=str(e))
            result.warnings.append("Subject parsing failed")

        try:
            # Parse body
            body_fields = self._parse_body_text(body)
            result.update(body_fields)
        except Exception as e:
            logger.warning("Body parsing failed", error=str(e))
            result.warnings.append("Body parsing failed")

        return result  # Return partial results

    except Exception as e:
        logger.error("Email parsing completely failed", error=str(e))
        # Return empty result - OCR will still work
        return EmailExtractionResult(
            overall_confidence=0.0,
            warnings=["Email parsing failed completely"]
        )
```

### 9.2 Fusion Errors

```python
class FusionError(Exception):
    """Base exception for data fusion."""
    pass

class ConflictResolutionError(FusionError):
    """Failed to resolve conflict between sources."""
    pass

# Graceful degradation
async def merge_extractions(
    email_extraction: EmailExtractionResult | None,
    ocr_extraction: ExtractionResult,
) -> FusedExtractionResult:
    try:
        if not email_extraction:
            # No email data - use OCR only
            return self._ocr_only_result(ocr_extraction)

        # Merge fields
        merged_claim = ExtractedClaim()
        conflicts = []

        for field in CLAIM_FIELDS:
            try:
                value, conf, source = self._merge_field(
                    field, email_extraction, ocr_extraction
                )
                setattr(merged_claim, field, value)
            except Exception as e:
                logger.warning(f"Field merge failed: {field}", error=str(e))
                # Fallback to OCR value
                value = getattr(ocr_extraction.claim, field)
                setattr(merged_claim, field, value)
                conflicts.append({
                    "field": field,
                    "error": str(e),
                    "fallback": "ocr"
                })

        return FusedExtractionResult(
            claim=merged_claim,
            conflicts=conflicts,
        )

    except Exception as e:
        logger.error("Fusion completely failed", error=str(e))
        # Fallback to OCR-only
        return self._ocr_only_result(ocr_extraction)
```

---

## 10. Performance Considerations

### 10.1 Email Body Caching

```python
# Cache email bodies in Redis (1 hour TTL)
CACHE_KEY = f"email:body:{message_id}"
TTL_SECONDS = 3600

async def get_email_body_cached(message_id: str) -> str:
    # Check cache
    cached = await redis.get(CACHE_KEY)
    if cached:
        return cached

    # Fetch from Gmail
    body = await gmail_service.get_message_body(message_id)

    # Cache it
    await redis.setex(CACHE_KEY, TTL_SECONDS, body)

    return body
```

### 10.2 Pattern Matching Optimization

```python
# Pre-compile regex patterns (class-level)
class EmailContentParser:
    def __init__(self):
        self._compiled_patterns = {
            field: [re.compile(p, re.IGNORECASE) for p in patterns]
            for field, patterns in ALL_PATTERNS.items()
        }

    def _extract_field(self, field_name: str, text: str):
        # Use pre-compiled patterns
        for pattern in self._compiled_patterns[field_name]:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None
```

### 10.3 Benchmarks (Target)

| Operation | Target Time | Notes |
|-----------|-------------|-------|
| Email text extraction | <50ms | Including HTML conversion |
| Email parsing (subject) | <10ms | Pattern matching |
| Email parsing (body) | <100ms | Full body analysis |
| Data fusion | <50ms | Merge 2 sources, 10 fields |
| Total overhead | <200ms | Additional time vs OCR-only |

### 10.4 Memory Optimization

```python
# Limit email body size
MAX_BODY_LENGTH = 10_000  # 10KB max

def clean_text(text: str) -> str:
    # Truncate if too long
    if len(text) > MAX_BODY_LENGTH:
        logger.warning("Email body truncated", original_length=len(text))
        text = text[:MAX_BODY_LENGTH]

    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)

    return text
```

---

## Appendix A: ASCII Component Diagram

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          EMAIL POLLER WORKER                               │
│                                                                            │
│  ┌──────────────┐       ┌────────────────────┐       ┌─────────────────┐ │
│  │ Gmail Inbox  │──────▶│ EmailTextExtractor │──────▶│ EmailContent    │ │
│  │              │       │ - extract_plain    │       │ Parser          │ │
│  │ (API Call)   │       │ - extract_html     │       │ - parse_subject │ │
│  └──────────────┘       │ - clean_text       │       │ - parse_body    │ │
│                         └────────────────────┘       │ - extract_*     │ │
│                                                       └─────────────────┘ │
│                                                              │            │
│                                                              ▼            │
│                                                    ┌───────────────────┐  │
│                                                    │ Email Extraction  │  │
│                                                    │ Result            │  │
│                                                    │ (with confidence) │  │
│                                                    └───────────────────┘  │
│                                                              │            │
│                                                              ▼            │
│                                                    ┌───────────────────┐  │
│                                                    │ Job + Email Data  │  │
│                                                    └───────────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Redis Queue (OCR Queue)
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         OCR PROCESSOR WORKER                               │
│                                                                            │
│  ┌─────────────┐        ┌──────────────┐        ┌──────────────────────┐ │
│  │ Job (with   │───────▶│ OCR Service  │───────▶│ OCR Extraction       │ │
│  │ email data) │        │ (PaddleOCR)  │        │ Result               │ │
│  └─────────────┘        └──────────────┘        └──────────────────────┘ │
│        │                                                   │              │
│        │ email_extraction                                 │              │
│        │                                                   │              │
│        ▼                                                   ▼              │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    DATA FUSION ENGINE                               │  │
│  │                                                                     │  │
│  │  ┌─────────────────┐         ┌────────────────────────────────┐   │  │
│  │  │ Email Extract   │         │ OCR Extract                    │   │  │
│  │  │ - member_id:0.8 │         │ - member_id:0.9                │   │  │
│  │  │ - amount:0.85   │  Merge  │ - amount:0.88                  │   │  │
│  │  │ - date:0.9      │ ──────▶ │ - provider:0.85                │   │  │
│  │  │ - name:0.75     │         │ - receipt_no:0.92              │   │  │
│  │  └─────────────────┘         └────────────────────────────────┘   │  │
│  │                                        │                           │  │
│  │                                        ▼                           │  │
│  │                              ┌──────────────────┐                  │  │
│  │                              │ Conflict         │                  │  │
│  │                              │ Resolution       │                  │  │
│  │                              │ - Compare values │                  │  │
│  │                              │ - Boost if match │                  │  │
│  │                              │ - Choose source  │                  │  │
│  │                              └──────────────────┘                  │  │
│  │                                        │                           │  │
│  │                                        ▼                           │  │
│  │                              ┌──────────────────┐                  │  │
│  │                              │ Fused Claim      │                  │  │
│  │                              │ - member_id:0.95 │                  │  │
│  │                              │ - amount:0.92    │                  │  │
│  │                              │ - date:0.90      │                  │  │
│  │                              │ - all fields     │                  │  │
│  │                              └──────────────────┘                  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                        │                                  │
│                                        ▼                                  │
│                              ┌──────────────────┐                         │
│                              │ Route by         │                         │
│                              │ Fused Confidence │                         │
│                              │ ≥90%: Auto       │                         │
│                              │ 75-89%: Review   │                         │
│                              │ <75%: Exception  │                         │
│                              └──────────────────┘                         │
└───────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Redis Queue (Submission Queue)
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                          NCB SUBMITTER WORKER                              │
│                                                                            │
│  ┌───────────────┐       ┌──────────────┐       ┌──────────────────────┐ │
│  │ Fused Claim   │──────▶│ NCB Service  │──────▶│ NCB API              │ │
│  │ (Merged)      │       │ (Existing)   │       │ (External)           │ │
│  └───────────────┘       └──────────────┘       └──────────────────────┘ │
│                                                                            │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix B: Sample Pattern Matching Results

### Example 1: Subject Line

**Input:**
```
Subject: Medical claim - Member ABC123 - RM150.00
```

**Extraction:**
```json
{
  "member_id": {
    "value": "ABC123",
    "confidence": 0.90,
    "source": "subject",
    "pattern_matched": "Member\\s*([A-Z0-9]+)"
  },
  "total_amount": {
    "value": 150.00,
    "confidence": 0.85,
    "source": "subject",
    "pattern_matched": "RM\\s*(\\d+\\.\\d{2})"
  }
}
```

### Example 2: Email Body

**Input:**
```
Dear TPA,

Please process the following claim:

Patient Name: Ahmad bin Abdullah
Member ID: ABC123
Service Date: 15/12/2024
Provider: Klinik Kesihatan Setiawangsa
Amount: RM150.00
Invoice #: INV-2024-12345

Receipt attached.
```

**Extraction:**
```json
{
  "member_name": {
    "value": "Ahmad bin Abdullah",
    "confidence": 0.88,
    "source": "body",
    "pattern_matched": "Patient\\s*Name[:\\s]+([A-Z][A-Za-z\\s.\\',\\-]+)"
  },
  "member_id": {
    "value": "ABC123",
    "confidence": 0.90,
    "source": "body",
    "pattern_matched": "Member\\s*ID[:\\s]+([A-Z0-9]+)"
  },
  "service_date": {
    "value": "2024-12-15T00:00:00",
    "confidence": 0.92,
    "source": "body",
    "pattern_matched": "Service\\s*Date[:\\s]+(\\d{1,2}[/.-]\\d{1,2}[/.-]\\d{4})"
  },
  "provider_name": {
    "value": "Klinik Kesihatan Setiawangsa",
    "confidence": 0.85,
    "source": "body",
    "pattern_matched": "Provider[:\\s]+([A-Z][A-Za-z\\s&.,'\\-]+)"
  },
  "total_amount": {
    "value": 150.00,
    "confidence": 0.88,
    "source": "body",
    "pattern_matched": "Amount[:\\s]+RM\\s*(\\d+\\.\\d{2})"
  },
  "receipt_number": {
    "value": "INV-2024-12345",
    "confidence": 0.90,
    "source": "body",
    "pattern_matched": "Invoice\\s*#[:\\s]+([A-Z0-9-]+)"
  }
}
```

---

## Appendix C: Fusion Examples

### Scenario 1: Perfect Agreement

**Email:**
- member_id: "ABC123" (0.90)
- amount: 150.00 (0.85)

**OCR:**
- member_id: "ABC123" (0.88)
- amount: 150.00 (0.90)
- provider: "Klinik Health" (0.85)

**Fusion:**
- member_id: "ABC123" (0.95) ← boosted +0.05
- amount: 150.00 (0.95) ← boosted +0.05
- provider: "Klinik Health" (0.85) ← OCR only

### Scenario 2: Conflict Resolution

**Email:**
- member_id: "ABC123" (0.85)
- amount: 150.00 (0.90)

**OCR:**
- member_id: "ABD123" (0.70)  ← OCR misread C as D
- amount: 150.00 (0.88)

**Fusion:**
- member_id: "ABC123" (0.85) ← Choose email (higher confidence)
  - Conflict: {"email": "ABC123", "ocr": "ABD123", "resolution": "email"}
- amount: 150.00 (0.95) ← Both agree, boost

### Scenario 3: Complementary Data

**Email:**
- member_id: "ABC123" (0.90)
- member_name: "Ahmad Abdullah" (0.88)
- service_date: "2024-12-15" (0.92)

**OCR:**
- member_id: "ABC123" (0.88)
- provider_name: "Klinik Health" (0.85)
- amount: 150.00 (0.90)
- receipt_number: "INV-123" (0.92)

**Fusion:**
- member_id: "ABC123" (0.95) ← Both sources
- member_name: "Ahmad Abdullah" (0.88) ← Email only
- service_date: "2024-12-15" (0.92) ← Email only
- provider_name: "Klinik Health" (0.85) ← OCR only
- amount: 150.00 (0.90) ← OCR only
- receipt_number: "INV-123" (0.92) ← OCR only

**Overall Confidence:** 0.90 (High)

---

## Document Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-26 | System Architect | Initial design document |

---

## Sign-off

This architecture design document requires approval from:

- [ ] Lead Engineer
- [ ] TPA Operations Manager
- [ ] Security Officer
- [ ] Product Owner

---

**END OF DOCUMENT**
