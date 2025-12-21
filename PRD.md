# Product Requirements Document (PRD)
## Claims Data Entry Agent

**Version:** 1.0  
**Author:** Armijn Mustapa  
**Status:** Proposed  
**Last Updated:** December 2024

---

## 1. Executive Summary

### 1.1 Problem Statement

Claims processors at our TPA spend significant time on repetitive data entry tasks:
- Opening emails manually
- Downloading attachments
- Reading receipt details
- Keying information into NCB

This manual process is time-consuming, error-prone, and limits daily claim processing capacity.

### 1.2 Proposed Solution

Deploy an AI-powered agent that automates extraction of claim data from emails and attachments, then enters structured data into NCB via API. The agent functions as a data entry assistant only—it does not perform claims adjudication or processing logic.

### 1.3 Key Value Proposition

- **80% reduction** in data entry time
- **Fewer keying errors** through OCR extraction
- **Faster intake** - claims in NCB within minutes of email receipt
- **Freed processor capacity** for adjudication and complex cases

---

## 2. Goals and Objectives

### 2.1 Business Goals

| Goal | Metric | Target |
|------|--------|--------|
| Reduce manual data entry | Time per claim | 80% reduction |
| Improve data accuracy | Error rate | <5% |
| Increase processing capacity | Claims per day | +40% |
| Achieve positive ROI | Payback period | 3-4 months |

### 2.2 Technical Goals

| Goal | Metric | Target |
|------|--------|--------|
| High extraction success | Success rate | ≥90% |
| Accurate OCR | Amount accuracy | ≥95% |
| Fast processing | Email to NCB | <5 minutes |
| Reliable submission | API success rate | ≥99% |

### 2.3 Non-Goals

This agent explicitly does NOT:
- Validate claims against policy rules or coverage limits
- Check member eligibility or benefit balances
- Approve or reject claims
- Communicate with members or providers
- Replace claims processors

---

## 3. User Personas

### 3.1 Primary: Claims Processor

**Role:** Processes incoming claims, reviews data, performs adjudication

**Current Pain Points:**
- Spends 60-70% of time on data entry
- Repetitive strain from manual keying
- Limited capacity for complex cases
- Transcription errors cause rework

**Needs from Agent:**
- Pre-populated claim records in NCB
- Clear flagging of uncertain extractions
- Easy access to original documents
- Confidence in data accuracy

### 3.2 Secondary: Operations Manager

**Role:** Oversees claims operations, monitors team productivity

**Current Pain Points:**
- Difficult to scale operations
- Quality inconsistencies across team
- Limited visibility into bottlenecks

**Needs from Agent:**
- Dashboard showing processing volumes
- Accuracy metrics and trends
- Exception queue visibility
- SLA monitoring

---

## 4. Functional Requirements

### 4.1 Email Monitoring (FR-100)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-101 | System shall poll designated Gmail inbox at configurable intervals (default: 30 seconds) | P0 |
| FR-102 | System shall identify emails with image/PDF attachments | P0 |
| FR-103 | System shall mark processed emails as read | P0 |
| FR-104 | System shall apply labels to processed emails | P1 |
| FR-105 | System shall handle multiple attachments per email | P0 |
| FR-106 | System shall skip emails without valid attachments | P0 |

### 4.2 Attachment Processing (FR-200)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-201 | System shall download attachments to temporary storage | P0 |
| FR-202 | System shall support JPEG, PNG, PDF, TIFF formats | P0 |
| FR-203 | System shall convert multi-page PDFs to individual images | P1 |
| FR-204 | System shall detect and reject corrupt/unreadable files | P0 |
| FR-205 | System shall compute hash for duplicate detection | P0 |

### 4.3 OCR Extraction (FR-300)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-301 | System shall use PaddleOCR-VL (0.9B) for text extraction | P0 |
| FR-302 | System shall support English, Malay, Chinese, Tamil languages | P0 |
| FR-303 | System shall extract structured fields from receipts | P0 |
| FR-304 | System shall calculate confidence score for each extraction | P0 |
| FR-305 | System shall handle rotated/skewed documents | P1 |
| FR-306 | System shall extract QR codes if present | P2 |

### 4.4 Data Structuring (FR-400)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-401 | System shall map extracted text to NCB API input schema | P0 |
| FR-402 | System shall parse monetary amounts (RM format) | P0 |
| FR-403 | System shall parse dates in Malaysian formats | P0 |
| FR-404 | System shall extract GST/SST amounts separately | P1 |
| FR-405 | System shall normalize provider names | P2 |

**Required Data Fields:**

| Field | Source | Required |
|-------|--------|----------|
| member_id | Email body or attachment | Yes |
| member_name | Email body or attachment | Yes |
| provider_name | Receipt | Yes |
| provider_address | Receipt | No |
| service_date | Receipt | Yes |
| receipt_number | Receipt | Yes |
| total_amount | Receipt | Yes |
| itemized_charges | Receipt | No |
| gst_sst_amount | Receipt | No |
| email_timestamp | Email metadata | Yes |
| attachment_filename | Email metadata | Yes |

### 4.5 NCB Integration (FR-500)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-501 | System shall submit extracted data to NCB API | P0 |
| FR-502 | System shall capture NCB claim reference number | P0 |
| FR-503 | System shall retry failed submissions with exponential backoff | P0 |
| FR-504 | System shall queue submissions when NCB is unavailable | P0 |
| FR-505 | System shall auto-retry queued submissions when NCB recovers | P0 |

### 4.6 Backup Storage (FR-600)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-601 | System shall log every extraction to Google Sheets | P0 |
| FR-602 | System shall archive attachments to Google Drive | P0 |
| FR-603 | System shall organize Drive files by date | P1 |
| FR-604 | System shall include processing metadata in Sheet entries | P0 |
| FR-605 | System shall serve as fallback when NCB is unavailable | P0 |

### 4.7 Exception Handling (FR-700)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-701 | System shall route low-confidence extractions to exception queue | P0 |
| FR-702 | System shall allow threshold configuration | P1 |
| FR-703 | System shall support random QA sampling | P1 |
| FR-704 | System shall notify staff of exception queue items | P1 |
| FR-705 | System shall provide manual override interface | P1 |

### 4.8 Admin Dashboard (FR-800)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-801 | Dashboard shall display processing statistics | P1 |
| FR-802 | Dashboard shall show exception queue | P1 |
| FR-803 | Dashboard shall display recent processing log | P1 |
| FR-804 | Dashboard shall show system health status | P1 |
| FR-805 | Dashboard shall support date range filtering | P2 |

---

## 5. Non-Functional Requirements

### 5.1 Performance (NFR-100)

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-101 | Email to NCB submission time | <5 minutes |
| NFR-102 | OCR processing time per image | <10 seconds |
| NFR-103 | Daily processing capacity | 500+ claims |
| NFR-104 | API response time (dashboard) | <500ms |

### 5.2 Reliability (NFR-200)

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-201 | System uptime | 99.5% |
| NFR-202 | Zero data loss | 100% |
| NFR-203 | Graceful degradation when NCB down | Required |
| NFR-204 | Automatic recovery after failures | Required |

### 5.3 Security (NFR-300)

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-301 | All processing on-premise | No external AI services |
| NFR-302 | PDPA compliance | Medical data handling |
| NFR-303 | Credentials in environment variables | No hardcoded secrets |
| NFR-304 | No PHI in application logs | Structured logging only |
| NFR-305 | TLS for all API communications | Required |

### 5.4 Maintainability (NFR-400)

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-401 | Containerized deployment | Docker |
| NFR-402 | Configuration via environment | 12-factor app |
| NFR-403 | Comprehensive logging | With correlation IDs |
| NFR-404 | Health check endpoints | For monitoring |

---

## 6. User Interface Requirements

### 6.1 Admin Dashboard

**Main Dashboard View:**
- Total emails processed (today/week/month)
- Success rate percentage
- Average confidence score
- Active exceptions count
- NCB submission status
- System health indicators

**Exception Queue View:**
- List of pending exceptions
- Original image preview
- OCR output display
- Manual edit capability
- Approve/reject actions

**Log View:**
- Searchable processing log
- Filter by status/date/confidence
- Export capability

### 6.2 Alert Notifications

**Daily Summary (Email):**
```
Claims Data Entry Summary – {DATE}
- {N} emails processed
- {M} submitted to NCB
- {X} exceptions queued
- Average confidence: {XX.X}%
```

**Exception Alert:**
```
Low confidence extraction: Email from {sender}
Received: {timestamp}
Issue: {description}
Action: Manual review required
```

**System Alert:**
```
NCB API unavailable since {timestamp}
{N} extractions queued pending submission
Status: Auto-retry in progress
```

---

## 7. Integration Requirements

### 7.1 Gmail API

| Aspect | Requirement |
|--------|-------------|
| Authentication | OAuth 2.0 with service account |
| Scopes | gmail.readonly, gmail.modify |
| Rate limits | Respect Google API quotas |
| Error handling | Retry with backoff on transient errors |

### 7.2 NCB API

| Aspect | Requirement |
|--------|-------------|
| Endpoint | POST /claims/submit (TBD) |
| Authentication | API key or OAuth (TBD) |
| Request format | JSON |
| Response | Claim reference number |
| Error handling | Queue on failure, retry |

### 7.3 Google Sheets API

| Aspect | Requirement |
|--------|-------------|
| Authentication | Service account |
| Sheet structure | One sheet per month |
| Columns | timestamp, email_id, extracted_data, ncb_status, ncb_ref |
| Error handling | Local backup if API fails |

### 7.4 Google Drive API

| Aspect | Requirement |
|--------|-------------|
| Authentication | Service account |
| Folder structure | /claims/{YYYY}/{MM}/{DD}/ |
| File naming | {email_id}_{original_filename} |
| Metadata | Processing timestamp, email ID |

---

## 8. ROI Analysis

### 8.1 Current State Costs

| Item | Value |
|------|-------|
| Claim emails per month | 2,000 |
| Manual entry time per claim | 5 minutes |
| Total monthly entry hours | 167 hours |
| Data entry clerk salary | RM 2,500/month |
| Hourly rate | RM 15/hour |
| Monthly data entry cost | RM 2,505 |

### 8.2 Post-Automation Projection

| Item | Value |
|------|-------|
| Time reduction | 80% |
| Remaining manual hours | 33 hours |
| Post-automation cost | RM 495/month |
| Monthly savings | RM 2,010 |
| Annual savings | RM 24,120 |

### 8.3 Implementation Costs (Estimated)

| Item | Cost |
|------|------|
| Hardware (if new GPU needed) | RM 3,000-8,000 |
| Development effort | 6-8 weeks |
| Google Workspace (existing) | RM 0 |
| Ongoing maintenance | Minimal |

### 8.4 Payback Period

**Target: 3-4 months** based on RM 2,010 monthly savings

---

## 9. Implementation Timeline

### Phase 1: Foundation (Weeks 1-2)

- NCB API schema discovery and documentation
- Gmail OAuth setup and inbox configuration
- Basic OCR pipeline with PaddleOCR-VL
- Core data models and extraction logic

### Phase 2: Integration (Weeks 3-4)

- Google Sheets backup implementation
- Google Drive archive implementation
- Admin dashboard (basic version)
- Exception handling workflow

### Phase 3: Pilot (Weeks 5-6)

- Deploy with live claim emails
- Tune OCR for Malaysian receipt formats
- Adjust confidence thresholds
- Collect accuracy metrics

### Phase 4: Production (Week 7+)

- Full production rollout
- Ongoing monitoring and optimization
- Staff training
- Documentation finalization

---

## 10. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| OCR accuracy below target | High | Medium | Tune thresholds, expand training data, fallback to manual |
| NCB API integration complexity | Medium | Medium | Early discovery session, flexible schema mapping |
| Gmail API rate limiting | Low | Low | Batch processing, caching |
| GPU hardware availability | Medium | Low | Cloud GPU fallback option |
| Staff resistance to change | Medium | Medium | Training, gradual rollout, demonstrate benefits |

---

## 11. Success Criteria

### 11.1 Pilot Success (Week 6)

- [ ] ≥85% extraction success rate
- [ ] ≥90% OCR accuracy on amounts
- [ ] <10 minute average processing time
- [ ] Zero data loss incidents
- [ ] Positive processor feedback

### 11.2 Production Success (Month 3)

- [ ] ≥90% extraction success rate
- [ ] ≥95% OCR accuracy on amounts
- [ ] <5 minute average processing time
- [ ] ≥80% data entry time reduction
- [ ] Positive ROI demonstrated

---

## 12. Dependencies

| Dependency | Owner | Status |
|------------|-------|--------|
| NCB API documentation | IT/NCB Team | Pending |
| Gmail inbox access | IT | Pending |
| Google Workspace service account | IT | Pending |
| GPU hardware procurement | IT/Finance | Pending |
| Claims processor training time | Operations | Pending |

---

## 13. Appendices

### Appendix A: Sample Malaysian Receipt Formats

Formats to support:
- Hospital itemized bills
- Clinic receipts
- Pharmacy receipts
- Lab test invoices
- Dental clinic receipts

### Appendix B: Language Support Matrix

| Language | Script | Priority |
|----------|--------|----------|
| English | Latin | P0 |
| Malay | Latin | P0 |
| Chinese (Simplified) | Han | P0 |
| Chinese (Traditional) | Han | P1 |
| Tamil | Tamil | P1 |

### Appendix C: PaddleOCR-VL Specifications

| Specification | Value |
|--------------|-------|
| Model size | 0.9B parameters |
| Disk size | ~2 GB |
| VRAM requirement | 4-8 GB |
| Languages | 109 |
| License | Apache 2.0 |
| Inference speed | 14% faster than alternatives |
