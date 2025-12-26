# Comprehensive Test Strategy: Email Extraction Enhancements

**Project:** Claims Data Entry Agent
**Feature:** Email Subject & Body Text Extraction
**Author:** Test Agent (Hive Mind Swarm)
**Date:** December 26, 2025
**Task ID:** task-1766744461462-1nheks3ad

---

## Executive Summary

This document outlines a comprehensive testing strategy for enhancing the email extraction capabilities to parse claim data directly from email subjects and body text, in addition to the existing OCR-based receipt extraction.

### Goals
- **90%+ code coverage** for email extraction logic
- **100% pattern coverage** for all extraction formats
- **All confidence thresholds validated** (≥90%, 75-89%, <75%)
- **All error paths tested** with appropriate recovery
- **Performance benchmarked** for concurrent processing

---

## 1. Unit Tests

### 1.1 Subject Line Parsing

**Test Suite:** `tests/unit/test_email_subject_parser.py`

#### Test Cases

```python
class TestSubjectLineParsing:
    """Test email subject line parsing for claim data extraction."""

    def test_parse_standard_subject_format(self):
        """
        Given: Subject "Medical Claim - December 2024"
        When: Subject parsed
        Then: Claim type identified as "medical", month/year extracted
        """

    def test_parse_subject_with_member_id(self):
        """
        Given: Subject "Claim for Member M12345 - Receipt Attached"
        When: Subject parsed
        Then: Member ID "M12345" extracted
        """

    def test_parse_subject_with_amount(self):
        """
        Given: Subject "Medical Claim RM 150.00"
        When: Subject parsed
        Then: Amount 150.00 and currency "MYR" extracted
        """

    def test_parse_subject_with_receipt_number(self):
        """
        Given: Subject "Claim Submission - INV-2024-12345"
        When: Subject parsed
        Then: Receipt number "INV-2024-12345" extracted
        """

    def test_parse_subject_with_service_date(self):
        """
        Given: Subject "Medical Claim 15/12/2024"
        When: Subject parsed
        Then: Service date "2024-12-15" extracted
        """

    def test_parse_subject_multiple_fields(self):
        """
        Given: Subject "Claim M12345 | RM 150.00 | 15/12/2024"
        When: Subject parsed
        Then: All fields (member_id, amount, date) extracted
        """

    def test_parse_subject_malay_format(self):
        """
        Given: Subject "Tuntutan Perubatan - Disember 2024"
        When: Subject parsed with language detection
        Then: Claim type identified, month/year extracted
        """

    def test_parse_subject_chinese_format(self):
        """
        Given: Subject "医疗索赔 - M12345 - 2024年12月"
        When: Subject parsed with Unicode support
        Then: Member ID and date extracted
        """

    def test_parse_subject_no_claim_info(self):
        """
        Given: Subject "Fwd: Re: Question about policy"
        When: Subject parsed
        Then: No claim data extracted, confidence = 0
        """

    def test_parse_subject_malformed_data(self):
        """
        Given: Subject "Claim M-INVALID RM abc.xyz 99/99/9999"
        When: Subject parsed
        Then: Invalid fields flagged, confidence reduced
        """


class TestSubjectPatternMatching:
    """Test pattern recognition in subject lines."""

    SUBJECT_PATTERNS = [
        # Standard formats
        "Medical Claim - December 2024",
        "Claim Submission for M12345",
        "Receipt INV-2024-001234 Attached",
        "RM 150.00 - Medical Expenses",

        # Date variations
        "Claim for 15/12/2024",
        "Claim for 15-12-2024",
        "Claim dated December 15, 2024",
        "Claim 15.12.2024",

        # Member ID formats
        "Member M12345 Claim",
        "Claim for M-12345",
        "Member ID: M12345",
        "M12345 - Medical Claim",

        # Amount formats
        "Claim RM150.00",
        "Claim RM 150.00",
        "Claim for MYR 150.00",
        "150.00 Malaysian Ringgit",

        # Receipt number formats
        "INV-2024-001234",
        "RCP-001234",
        "Receipt No: 12345",
        "Invoice #2024-001234",

        # Multilingual
        "Tuntutan Perubatan M12345",
        "医疗索赔 - M12345",
        "மருத்துவ உரிமைகோரல்",
    ]

    @pytest.mark.parametrize("subject", SUBJECT_PATTERNS)
    def test_all_subject_patterns(self, subject):
        """
        Test that all documented subject patterns are recognized.
        """
```

---

### 1.2 Body Text Extraction

**Test Suite:** `tests/unit/test_email_body_parser.py`

#### Test Cases

```python
class TestBodyTextExtraction:
    """Test extraction from email body (plain text)."""

    def test_extract_from_plain_text_body(self):
        """
        Given: Plain text email body with claim details
        When: Body parsed
        Then: All structured fields extracted

        Sample body:
        '''
        Dear Claims Team,

        Please process claim for:
        Member ID: M12345
        Member Name: John Doe
        Service Date: 15/12/2024
        Provider: City Medical Centre
        Amount: RM 150.00
        Receipt: INV-2024-001234

        Thank you.
        '''
        """

    def test_extract_from_structured_body(self):
        """
        Given: Email body with structured key-value format
        When: Body parsed
        Then: All fields mapped correctly

        Sample:
        '''
        Member ID: M12345
        Name: John Doe
        Date of Service: 15/12/2024
        Medical Provider: City Medical Centre
        Total Amount: RM 150.00
        Invoice Number: INV-2024-001234
        '''
        """

    def test_extract_from_conversational_body(self):
        """
        Given: Conversational email with embedded data
        When: NLP extraction performed
        Then: Key fields extracted from natural text

        Sample:
        '''
        Hi,

        I'm submitting a medical claim for my visit to City Medical
        Centre on 15th December. The total bill was RM 150.00 and
        my member ID is M12345. Invoice number is INV-2024-001234.

        Regards,
        John Doe
        '''
        """

    def test_extract_from_multiline_itemized_body(self):
        """
        Given: Email with itemized charges in body
        When: Body parsed with table detection
        Then: Itemized charges extracted as list

        Sample:
        '''
        Consultation:    RM  80.00
        Medication:      RM  70.00
        SST (6%):        RM   9.00
        ---------------------------
        Total:           RM 159.00
        '''
        """

    def test_extract_malaysian_format_body(self):
        """
        Given: Email body in Malay language
        When: Language-aware parsing performed
        Then: Fields extracted using Malay patterns
        """

    def test_extract_chinese_format_body(self):
        """
        Given: Email body in Chinese
        When: Unicode-aware parsing performed
        Then: Fields extracted with Chinese patterns
        """

    def test_extract_html_body(self):
        """
        Given: HTML email body with formatting
        When: HTML parsed and converted to text
        Then: Claim data extracted from stripped text
        """

    def test_extract_multipart_body(self):
        """
        Given: Multipart email (plain + HTML)
        When: Both parts analyzed
        Then: Best available content used for extraction
        """


class TestBodyFieldExtraction:
    """Test individual field extraction from body text."""

    def test_extract_member_id_patterns(self):
        """Test various member ID formats in body text."""
        patterns = [
            ("Member ID: M12345", "M12345"),
            ("Member: M12345", "M12345"),
            ("ID M12345", "M12345"),
            ("M12345 member", "M12345"),
            ("Ahli: M12345", "M12345"),  # Malay
        ]

    def test_extract_member_name_patterns(self):
        """Test member name extraction."""
        patterns = [
            ("Member Name: John Doe", "John Doe"),
            ("Name: Ahmad bin Ali", "Ahmad bin Ali"),
            ("Patient: Siti Nurhaliza", "Siti Nurhaliza"),
            ("Nama: Ahmad bin Ali", "Ahmad bin Ali"),  # Malay
        ]

    def test_extract_date_patterns(self):
        """Test service date extraction."""
        patterns = [
            ("Service Date: 15/12/2024", "2024-12-15"),
            ("Date: 15-12-2024", "2024-12-15"),
            ("on December 15, 2024", "2024-12-15"),
            ("Tarikh: 15/12/2024", "2024-12-15"),  # Malay
        ]

    def test_extract_amount_patterns(self):
        """Test amount extraction."""
        patterns = [
            ("Amount: RM 150.00", 150.00),
            ("Total: RM150.00", 150.00),
            ("MYR 150.00", 150.00),
            ("150.00 ringgit", 150.00),
            ("Jumlah: RM 150.00", 150.00),  # Malay
        ]

    def test_extract_provider_patterns(self):
        """Test provider name extraction."""
        patterns = [
            ("Provider: City Medical Centre", "City Medical Centre"),
            ("Clinic: Klinik Kesihatan", "Klinik Kesihatan"),
            ("Hospital: Hospital Kuala Lumpur", "Hospital Kuala Lumpur"),
        ]

    def test_extract_receipt_number_patterns(self):
        """Test receipt/invoice number extraction."""
        patterns = [
            ("Invoice: INV-2024-001234", "INV-2024-001234"),
            ("Receipt No: RCP-001234", "RCP-001234"),
            ("Invoice Number: INV-2024-001234", "INV-2024-001234"),
        ]
```

---

### 1.3 Confidence Scoring Logic

**Test Suite:** `tests/unit/test_email_extraction_confidence.py`

#### Test Cases

```python
class TestEmailExtractionConfidence:
    """Test confidence scoring for email-extracted data."""

    def test_confidence_all_required_fields_present(self):
        """
        Given: Email with all required fields extracted
        When: Confidence calculated
        Then: Score ≥ 0.90 (HIGH confidence)
        """

    def test_confidence_missing_optional_fields(self):
        """
        Given: Email with required fields but missing optional ones
        When: Confidence calculated
        Then: Score 0.75-0.89 (MEDIUM confidence)
        """

    def test_confidence_missing_critical_field(self):
        """
        Given: Email missing member_id or total_amount
        When: Confidence calculated
        Then: Score < 0.75 (LOW confidence)
        """

    def test_confidence_field_validation_fails(self):
        """
        Given: Extracted fields fail validation (invalid date, negative amount)
        When: Confidence calculated
        Then: Confidence penalized appropriately
        """

    def test_confidence_multiple_conflicting_values(self):
        """
        Given: Email contains conflicting data (2 different amounts)
        When: Confidence calculated
        Then: Confidence reduced, ambiguity flagged
        """

    def test_confidence_source_reliability(self):
        """
        Given: Subject vs Body vs Attachment have different values
        When: Confidence calculated for each source
        Then: Most reliable source weighted higher
        """

    def test_confidence_pattern_strength(self):
        """
        Given: Strongly-typed format (key: value) vs weak pattern (conversational)
        When: Confidence calculated
        Then: Structured format scores higher
        """


class TestConfidenceThresholds:
    """Test confidence threshold routing."""

    @pytest.mark.parametrize("score,expected_level,expected_action", [
        (0.95, "HIGH", "auto_submit"),
        (0.90, "HIGH", "auto_submit"),
        (0.89, "MEDIUM", "submit_with_review"),
        (0.75, "MEDIUM", "submit_with_review"),
        (0.74, "LOW", "exception_queue"),
        (0.50, "LOW", "exception_queue"),
        (0.00, "LOW", "exception_queue"),
    ])
    def test_confidence_routing(self, score, expected_level, expected_action):
        """Test that confidence scores route to correct processing path."""

    def test_combined_confidence_ocr_and_email(self):
        """
        Given: Data from both OCR (attachment) and email text
        When: Combined confidence calculated
        Then: Higher of the two used, or average if both high
        """
```

---

### 1.4 Error Handling

**Test Suite:** `tests/unit/test_email_extraction_errors.py`

#### Test Cases

```python
class TestEmailExtractionErrorHandling:
    """Test error handling in email extraction."""

    def test_handle_empty_subject(self):
        """
        Given: Email with empty subject
        When: Extraction attempted
        Then: Gracefully handled, no crash
        """

    def test_handle_empty_body(self):
        """
        Given: Email with empty body
        When: Extraction attempted
        Then: Returns empty result, no exception
        """

    def test_handle_malformed_encoding(self):
        """
        Given: Email with corrupted character encoding
        When: Body decoded
        Then: Encoding errors handled gracefully
        """

    def test_handle_oversized_body(self):
        """
        Given: Email body > 1MB
        When: Parsing attempted
        Then: Truncated or rejected with warning
        """

    def test_handle_invalid_unicode(self):
        """
        Given: Email with invalid Unicode sequences
        When: Text processing performed
        Then: Invalid chars replaced or skipped
        """

    def test_handle_extraction_timeout(self):
        """
        Given: Complex body taking >30s to parse
        When: Timeout reached
        Then: Partial results returned, timeout logged
        """

    def test_handle_regex_catastrophic_backtracking(self):
        """
        Given: Malicious input causing regex DoS
        When: Pattern matching performed
        Then: Regex timeout prevents hang
        """
```

---

## 2. Integration Tests

### 2.1 Email → Extraction → NCB Flow

**Test Suite:** `tests/integration/test_email_extraction_flow.py`

#### Test Cases

```python
class TestEmailExtractionIntegration:
    """Test complete email extraction pipeline."""

    @pytest.mark.asyncio
    async def test_email_with_subject_data_only(self):
        """
        Given: Email with claim data in subject, no attachment
        When: Email processed
        Then: Data extracted from subject, queued for NCB submission
        """

    @pytest.mark.asyncio
    async def test_email_with_body_data_only(self):
        """
        Given: Email with claim data in body, no attachment
        When: Email processed
        Then: Data extracted from body, queued for NCB submission
        """

    @pytest.mark.asyncio
    async def test_email_with_attachment_and_text(self):
        """
        Given: Email with both text data and attachment
        When: Email processed
        Then: Both sources extracted, best data used
        """

    @pytest.mark.asyncio
    async def test_email_data_overrides_ocr(self):
        """
        Given: High-confidence email data, low-confidence OCR
        When: Conflict resolution applied
        Then: Email data takes precedence
        """

    @pytest.mark.asyncio
    async def test_ocr_data_overrides_email(self):
        """
        Given: Low-confidence email data, high-confidence OCR
        When: Conflict resolution applied
        Then: OCR data takes precedence
        """

    @pytest.mark.asyncio
    async def test_email_extraction_to_sheets_logging(self):
        """
        Given: Email data extracted
        When: Logged to Google Sheets
        Then: Source marked as "email_text" vs "ocr"
        """

    @pytest.mark.asyncio
    async def test_email_extraction_to_drive_archive(self):
        """
        Given: Email processed with text extraction
        When: Archived to Drive
        Then: Original email saved with metadata
        """


class TestExceptionQueueRouting:
    """Test low-confidence routing to exception queue."""

    @pytest.mark.asyncio
    async def test_low_confidence_email_to_exception_queue(self):
        """
        Given: Email extraction confidence < 75%
        When: Processing completed
        Then: Routed to exception queue, not NCB
        """

    @pytest.mark.asyncio
    async def test_exception_queue_manual_review(self):
        """
        Given: Email in exception queue
        When: Admin reviews via dashboard
        Then: Can approve/reject/edit extracted data
        """
```

---

### 2.2 Multipart Email Handling

**Test Suite:** `tests/integration/test_multipart_emails.py`

#### Test Cases

```python
class TestMultipartEmailProcessing:
    """Test complex email formats."""

    @pytest.mark.asyncio
    async def test_multipart_alternative(self):
        """
        Given: Email with both plain text and HTML parts
        When: Both parts parsed
        Then: Best extraction from either part used
        """

    @pytest.mark.asyncio
    async def test_multipart_mixed_with_attachments(self):
        """
        Given: Multipart email with text + multiple attachments
        When: All parts processed
        Then: Text and all attachments extracted
        """

    @pytest.mark.asyncio
    async def test_html_table_extraction(self):
        """
        Given: HTML email with table of charges
        When: HTML parsed
        Then: Itemized charges extracted from table
        """

    @pytest.mark.asyncio
    async def test_inline_images(self):
        """
        Given: Email with inline images (cid:)
        When: Email processed
        Then: Inline images extracted as attachments
        """
```

---

### 2.3 Multi-Language Support

**Test Suite:** `tests/integration/test_multilingual_extraction.py`

#### Test Cases

```python
class TestMultilingualExtraction:
    """Test extraction in multiple languages."""

    @pytest.mark.asyncio
    async def test_english_email_extraction(self):
        """Full English email end-to-end."""

    @pytest.mark.asyncio
    async def test_malay_email_extraction(self):
        """Full Malay email end-to-end."""

    @pytest.mark.asyncio
    async def test_chinese_email_extraction(self):
        """Full Chinese email end-to-end."""

    @pytest.mark.asyncio
    async def test_tamil_email_extraction(self):
        """Full Tamil email end-to-end."""

    @pytest.mark.asyncio
    async def test_mixed_language_email(self):
        """
        Given: Email with mixed English/Malay
        When: Multi-language detection enabled
        Then: All languages processed correctly
        """
```

---

## 3. Test Data

### 3.1 Sample Email Subjects

**File:** `tests/fixtures/sample_email_subjects.json`

```json
{
  "standard_formats": [
    "Medical Claim - December 2024",
    "Claim Submission for M12345",
    "Receipt INV-2024-001234 Attached",
    "Claim for RM 150.00"
  ],

  "with_member_id": [
    "Medical Claim - M12345",
    "Claim for Member M12345",
    "M12345 - Medical Expenses"
  ],

  "with_amounts": [
    "Claim RM 150.00",
    "Medical Claim - RM150.00",
    "Claim for MYR 150.00"
  ],

  "with_dates": [
    "Claim 15/12/2024",
    "Medical Claim - 15-12-2024",
    "Claim dated December 15, 2024"
  ],

  "multilingual": [
    "Tuntutan Perubatan - Disember 2024",
    "医疗索赔 - M12345",
    "மருத்துவ உரிமைகோரல் - M12345"
  ],

  "edge_cases": [
    "Fwd: Re: Medical Claim",
    "URGENT: Claim Submission",
    "",
    "No claim info here",
    "Claim M-INVALID RM abc.xyz"
  ]
}
```

---

### 3.2 Sample Email Bodies

**File:** `tests/fixtures/sample_email_bodies/`

#### `structured_english.txt`
```
Member ID: M12345
Member Name: John Doe
Service Date: 15/12/2024
Provider: City Medical Centre
Provider Address: 123 Main St, Kuala Lumpur
Amount: RM 150.00
Receipt Number: INV-2024-001234
SST (6%): RM 9.00
Total: RM 159.00
```

#### `conversational_english.txt`
```
Dear Claims Team,

I visited City Medical Centre on 15th December 2024 for a routine
consultation. The total bill came to RM 150.00 (plus SST of RM 9.00,
making it RM 159.00 total).

My member ID is M12345 and the invoice number is INV-2024-001234.

Please process this claim at your earliest convenience.

Best regards,
John Doe
```

#### `structured_malay.txt`
```
No. Ahli: M67890
Nama Ahli: Ahmad bin Ali
Tarikh Perkhidmatan: 15-12-2024
Pembekal: Klinik Kesihatan Jaya
Jumlah: RM 100.00
No. Resit: INV-2024-5678
SST (6%): RM 6.00
Jumlah Keseluruhan: RM 106.00
```

#### `conversational_malay.txt`
```
Assalamualaikum,

Saya ingin mengemukakan tuntutan perubatan untuk lawatan saya ke
Klinik Kesihatan Jaya pada 15 Disember 2024. Jumlah bil adalah
RM 100.00 (termasuk SST RM 6.00).

No. Ahli saya: M67890
No. Resit: INV-2024-5678

Terima kasih.

Ahmad bin Ali
```

#### `html_formatted.html`
```html
<html>
<body>
  <p><strong>Member ID:</strong> M12345</p>
  <p><strong>Name:</strong> John Doe</p>
  <p><strong>Service Date:</strong> 15/12/2024</p>

  <table>
    <tr><td>Consultation</td><td>RM 80.00</td></tr>
    <tr><td>Medication</td><td>RM 70.00</td></tr>
    <tr><td>SST (6%)</td><td>RM 9.00</td></tr>
    <tr><td><strong>Total</strong></td><td><strong>RM 159.00</strong></td></tr>
  </table>

  <p>Invoice: INV-2024-001234</p>
</body>
</html>
```

#### `chinese_mixed.txt`
```
会员编号: M12345
会员姓名: 李明
服务日期: 15/12/2024
医疗提供者: City Medical Centre (城市医疗中心)
总金额: RM 150.00
发票号码: INV-2024-001234
```

---

### 3.3 Edge Cases

**File:** `tests/fixtures/edge_case_emails.json`

```json
{
  "empty_subject": {
    "subject": "",
    "body": "Member M12345, Amount RM 150.00",
    "expected_confidence": "LOW"
  },

  "empty_body": {
    "subject": "Medical Claim M12345 RM 150.00",
    "body": "",
    "expected_confidence": "MEDIUM"
  },

  "missing_critical_fields": {
    "subject": "Medical Claim",
    "body": "I visited the doctor yesterday.",
    "expected_fields": [],
    "expected_confidence": "LOW"
  },

  "conflicting_data": {
    "subject": "Claim RM 150.00",
    "body": "Total amount: RM 200.00",
    "expected_action": "flag_conflict"
  },

  "malformed_data": {
    "subject": "Claim M-INVALID RM abc.xyz 99/99/9999",
    "body": "Member: #@!$%",
    "expected_validation_errors": ["member_id", "amount", "service_date"]
  },

  "oversized_body": {
    "body_size_mb": 5,
    "expected_action": "truncate_or_reject"
  },

  "invalid_encoding": {
    "encoding": "invalid_utf8",
    "expected_action": "fallback_to_ascii"
  }
}
```

---

## 4. Test Coverage Goals

### 4.1 Code Coverage Targets

| Component | Target Coverage | Priority |
|-----------|----------------|----------|
| **Email Subject Parser** | 95%+ | HIGH |
| **Email Body Parser** | 90%+ | HIGH |
| **Field Extractors** | 95%+ | HIGH |
| **Confidence Calculator** | 100% | CRITICAL |
| **Error Handlers** | 90%+ | HIGH |
| **Integration Points** | 85%+ | MEDIUM |

### 4.2 Pattern Coverage

**All extraction patterns must have tests:**
- ✅ Member ID formats (M12345, M-12345, etc.)
- ✅ Date formats (DD/MM/YYYY, DD-MM-YYYY, Month DD YYYY)
- ✅ Amount formats (RM 150.00, RM150.00, MYR 150.00)
- ✅ Receipt formats (INV-*, RCP-*, etc.)
- ✅ Provider names (various formats)
- ✅ Multi-language keywords (English, Malay, Chinese, Tamil)

### 4.3 Error Path Coverage

**All error scenarios tested:**
- ✅ Empty/missing fields
- ✅ Invalid data types
- ✅ Encoding errors
- ✅ Timeout conditions
- ✅ Regex failures
- ✅ Conflicting data
- ✅ Size limits exceeded

---

## 5. Performance Tests

### 5.1 Extraction Speed Benchmarks

**Test Suite:** `tests/performance/test_email_extraction_speed.py`

#### Test Cases

```python
class TestEmailExtractionPerformance:
    """Test extraction performance."""

    def test_subject_parsing_speed(self):
        """
        Given: 1000 email subjects
        When: All parsed sequentially
        Then: Average parsing time < 10ms per subject
        """

    def test_body_parsing_speed_plain_text(self):
        """
        Given: 1000 plain text email bodies (avg 500 words)
        When: All parsed sequentially
        Then: Average parsing time < 50ms per body
        """

    def test_body_parsing_speed_html(self):
        """
        Given: 1000 HTML email bodies
        When: All parsed with HTML conversion
        Then: Average parsing time < 100ms per body
        """

    def test_extraction_vs_ocr_speed(self):
        """
        Given: Same data in email vs attachment
        When: Both methods timed
        Then: Email extraction at least 10x faster than OCR
        """


class TestConcurrentProcessing:
    """Test concurrent email processing."""

    @pytest.mark.asyncio
    async def test_concurrent_email_extraction(self):
        """
        Given: 100 emails to process
        When: Processed concurrently (10 workers)
        Then: Throughput > 50 emails/second
        """

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self):
        """
        Given: 1000 emails processed concurrently
        When: Memory monitored
        Then: Memory usage < 500MB, no leaks
        """

    @pytest.mark.asyncio
    async def test_queue_backpressure(self):
        """
        Given: 10,000 emails arrive suddenly
        When: Queue processes with backpressure
        Then: No crashes, graceful degradation
        """
```

---

### 5.2 Performance Benchmarks

**File:** `tests/performance/benchmarks.json`

```json
{
  "targets": {
    "subject_parsing": {
      "max_time_ms": 10,
      "throughput_per_sec": 1000
    },
    "body_parsing_plain": {
      "max_time_ms": 50,
      "throughput_per_sec": 200
    },
    "body_parsing_html": {
      "max_time_ms": 100,
      "throughput_per_sec": 100
    },
    "concurrent_processing": {
      "workers": 10,
      "throughput_per_sec": 50,
      "max_memory_mb": 500
    }
  }
}
```

---

## 6. Test Execution Plan

### 6.1 Test Pyramid Distribution

```
         /\
        /E2E\          15% - End-to-End Tests (15 tests)
       /------\         - Full email → NCB flow
      /Integr. \       25% - Integration Tests (25 tests)
     /----------\       - Email extraction pipeline
    /   Unit     \     60% - Unit Tests (60 tests)
   /--------------\     - Parsers, extractors, validators
```

**Total: ~100 new tests for email extraction**

### 6.2 CI/CD Integration

```yaml
# .github/workflows/email-extraction-tests.yml
name: Email Extraction Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Run Unit Tests
        run: pytest tests/unit/test_email_*.py -v --cov

      - name: Run Integration Tests
        run: pytest tests/integration/test_email_*.py -v

      - name: Run Performance Tests
        run: pytest tests/performance/test_email_*.py -v

      - name: Coverage Report
        run: |
          coverage report --fail-under=90
          coverage html
```

### 6.3 Test Execution Order

1. **Unit Tests** (fastest, run first)
   - Subject parsers
   - Body parsers
   - Field extractors
   - Confidence calculators

2. **Integration Tests** (slower, mock external services)
   - Email → extraction flow
   - Exception queue routing
   - Multi-source conflict resolution

3. **Performance Tests** (slowest, run last)
   - Speed benchmarks
   - Concurrent processing
   - Memory profiling

---

## 7. Expected Test Outcomes

### 7.1 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Code Coverage** | ≥90% | pytest-cov |
| **All Patterns Tested** | 100% | Manual checklist |
| **Confidence Thresholds** | 100% tested | Parametrized tests |
| **Error Paths** | 100% covered | Branch coverage |
| **Performance** | All benchmarks pass | pytest-benchmark |
| **Zero Regressions** | All existing tests pass | CI/CD pipeline |

### 7.2 Test Reporting

**Generate comprehensive reports:**

```bash
# HTML coverage report
pytest --cov=src --cov-report=html tests/

# Performance benchmark report
pytest tests/performance/ --benchmark-only --benchmark-json=benchmark.json

# Test results summary
pytest tests/ -v --tb=short --html=report.html
```

### 7.3 Quality Gates

**Tests must pass before merge:**
- ✅ All unit tests pass (100%)
- ✅ All integration tests pass (100%)
- ✅ Code coverage ≥ 90%
- ✅ No critical security issues
- ✅ Performance benchmarks met
- ✅ No memory leaks detected

---

## 8. Test Maintenance

### 8.1 Test Data Management

**Location:** `tests/fixtures/`

```
tests/fixtures/
├── sample_email_subjects.json
├── sample_email_bodies/
│   ├── structured_english.txt
│   ├── conversational_english.txt
│   ├── structured_malay.txt
│   ├── conversational_malay.txt
│   ├── html_formatted.html
│   └── chinese_mixed.txt
├── edge_case_emails.json
└── performance_datasets/
    ├── 1000_subjects.json
    ├── 1000_bodies_plain.json
    └── 1000_bodies_html.json
```

### 8.2 Test Update Triggers

**Update tests when:**
- New extraction pattern added
- New language supported
- Confidence algorithm changed
- API contract modified
- Bug discovered in production

### 8.3 Regression Prevention

**Capture production issues as tests:**

```python
def test_regression_issue_123():
    """
    Regression test for Issue #123: Chinese member names truncated.

    Given: Email with Chinese member name
    When: Name extracted
    Then: Full name preserved, not truncated
    """
```

---

## 9. Implementation Checklist

### Phase 1: Unit Tests (Week 1)
- [ ] Create test file structure
- [ ] Implement subject parser tests
- [ ] Implement body parser tests
- [ ] Implement field extractor tests
- [ ] Implement confidence tests
- [ ] Implement error handling tests
- [ ] Achieve 90% unit test coverage

### Phase 2: Test Data (Week 1)
- [ ] Create sample subjects JSON
- [ ] Create sample bodies (all languages)
- [ ] Create edge case examples
- [ ] Generate performance datasets

### Phase 3: Integration Tests (Week 2)
- [ ] Implement email → extraction flow tests
- [ ] Implement multipart email tests
- [ ] Implement multi-language tests
- [ ] Implement exception queue tests

### Phase 4: Performance Tests (Week 2)
- [ ] Implement speed benchmarks
- [ ] Implement concurrent processing tests
- [ ] Implement memory profiling tests
- [ ] Document performance baselines

### Phase 5: CI/CD Integration (Week 2)
- [ ] Add GitHub Actions workflow
- [ ] Configure coverage reporting
- [ ] Set up performance tracking
- [ ] Add quality gates

---

## 10. Coordination Protocol

### Before Testing Starts
```bash
npx claude-flow@alpha hooks pre-task --description "Execute email extraction test suite"
npx claude-flow@alpha hooks session-restore --session-id "swarm-1766744269580-ho5meqttz"
```

### During Testing
```bash
# After each major test file created
npx claude-flow@alpha hooks post-edit \
  --file "tests/unit/test_email_subject_parser.py" \
  --memory-key "swarm/tester/subject_parser_tests"

# Notify progress
npx claude-flow@alpha hooks notify \
  --message "Unit tests for subject parsing: 15/15 passing"
```

### After Testing Complete
```bash
npx claude-flow@alpha hooks post-task --task-id "task-1766744461462-1nheks3ad"
npx claude-flow@alpha hooks session-end --export-metrics true
```

---

## Appendix A: Test File Structure

```
tests/
├── unit/
│   ├── test_email_subject_parser.py
│   ├── test_email_body_parser.py
│   ├── test_email_field_extractors.py
│   ├── test_email_extraction_confidence.py
│   └── test_email_extraction_errors.py
├── integration/
│   ├── test_email_extraction_flow.py
│   ├── test_multipart_emails.py
│   └── test_multilingual_extraction.py
├── performance/
│   ├── test_email_extraction_speed.py
│   └── benchmarks.json
└── fixtures/
    ├── sample_email_subjects.json
    ├── sample_email_bodies/
    ├── edge_case_emails.json
    └── performance_datasets/
```

---

## Appendix B: Sample Test Implementation

```python
"""
Sample implementation: tests/unit/test_email_subject_parser.py
"""
import pytest
from src.services.email_extractor import EmailSubjectParser


class TestSubjectLineParsing:
    """Test email subject line parsing for claim data extraction."""

    @pytest.fixture
    def parser(self):
        return EmailSubjectParser()

    def test_parse_subject_with_member_id(self, parser):
        """
        Given: Subject "Claim for Member M12345 - Receipt Attached"
        When: Subject parsed
        Then: Member ID "M12345" extracted
        """
        # Arrange
        subject = "Claim for Member M12345 - Receipt Attached"

        # Act
        result = parser.parse(subject)

        # Assert
        assert result.member_id == "M12345"
        assert result.confidence >= 0.80
        assert "member_id" in result.extracted_fields

    def test_parse_subject_with_amount(self, parser):
        """
        Given: Subject "Medical Claim RM 150.00"
        When: Subject parsed
        Then: Amount 150.00 and currency "MYR" extracted
        """
        # Arrange
        subject = "Medical Claim RM 150.00"

        # Act
        result = parser.parse(subject)

        # Assert
        assert result.total_amount == 150.00
        assert result.currency == "MYR"
        assert result.confidence >= 0.75
```

---

**END OF TEST STRATEGY**

**Next Steps:**
1. Review and approve this test strategy
2. Implement unit tests (Phase 1)
3. Create test data fixtures (Phase 2)
4. Implement integration tests (Phase 3)
5. Add performance tests (Phase 4)
6. Integrate into CI/CD (Phase 5)

**Estimated Effort:** 2 weeks for complete implementation
**Expected Outcome:** 90%+ coverage, robust email extraction testing
