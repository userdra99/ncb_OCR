# API Contracts
## Claims Data Entry Agent

**Version:** 1.0  
**Last Updated:** December 2024

---

## 1. Internal REST API

Base URL: `http://localhost:8080/api/v1`

### 1.1 Authentication

All endpoints require API key authentication:

```http
Authorization: Bearer {ADMIN_API_KEY}
```

### 1.2 Common Response Format

**Success Response:**
```json
{
    "success": true,
    "data": { ... },
    "meta": {
        "timestamp": "2024-12-18T10:42:00Z",
        "request_id": "req_abc123"
    }
}
```

**Error Response:**
```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid date format",
        "details": { ... }
    },
    "meta": {
        "timestamp": "2024-12-18T10:42:00Z",
        "request_id": "req_abc123"
    }
}
```

---

## 2. Health Endpoints

### GET /health

Basic health check.

**Response:**
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "uptime_seconds": 86400
}
```

### GET /health/detailed

Detailed component health.

**Response:**
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "uptime_seconds": 86400,
    "components": {
        "redis": {
            "status": "connected",
            "latency_ms": 2
        },
        "gmail": {
            "status": "connected",
            "last_poll": "2024-12-18T10:41:30Z"
        },
        "ncb_api": {
            "status": "connected",
            "latency_ms": 150
        },
        "google_sheets": {
            "status": "connected"
        },
        "google_drive": {
            "status": "connected"
        },
        "ocr_engine": {
            "status": "ready",
            "gpu_available": true,
            "model_loaded": true
        }
    },
    "workers": {
        "email_poller": {
            "status": "running",
            "last_run": "2024-12-18T10:41:30Z"
        },
        "ocr_processor": {
            "status": "running",
            "jobs_in_queue": 3
        },
        "ncb_submitter": {
            "status": "running",
            "jobs_in_queue": 1
        }
    }
}
```

---

## 3. Jobs Endpoints

### GET /jobs

List processing jobs with filtering.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | all | Filter by status |
| limit | int | 50 | Results per page (max 100) |
| offset | int | 0 | Pagination offset |
| date_from | datetime | - | Filter by creation date |
| date_to | datetime | - | Filter by creation date |
| email_id | string | - | Filter by source email |
| sort | string | -created_at | Sort field (prefix - for desc) |

**Example Request:**
```http
GET /api/v1/jobs?status=exception&limit=20&sort=-created_at
```

**Response:**
```json
{
    "success": true,
    "data": {
        "jobs": [
            {
                "id": "job_abc123",
                "email_id": "msg_xyz789",
                "attachment_filename": "receipt_001.jpg",
                "status": "exception",
                "confidence_score": 0.72,
                "confidence_level": "low",
                "ncb_reference": null,
                "error_message": "Amount field unclear",
                "created_at": "2024-12-18T10:42:00Z",
                "updated_at": "2024-12-18T10:42:05Z"
            }
        ],
        "pagination": {
            "total": 142,
            "limit": 20,
            "offset": 0,
            "has_more": true
        }
    }
}
```

### GET /jobs/{job_id}

Get single job details.

**Response:**
```json
{
    "success": true,
    "data": {
        "id": "job_abc123",
        "email_id": "msg_xyz789",
        "attachment_filename": "receipt_001.jpg",
        "attachment_hash": "sha256:abc123...",
        "status": "extracted",
        "extraction_result": {
            "claim": {
                "member_id": "M12345",
                "member_name": "John Doe",
                "provider_name": "City Medical Centre",
                "provider_address": "123 Main St, KL",
                "service_date": "2024-12-15",
                "receipt_number": "RCP-2024-001234",
                "total_amount": 150.00,
                "currency": "MYR",
                "itemized_charges": [
                    {"description": "Consultation", "amount": 80.00},
                    {"description": "Medication", "amount": 70.00}
                ],
                "gst_amount": null,
                "sst_amount": 9.00
            },
            "confidence_score": 0.94,
            "confidence_level": "high",
            "field_confidences": {
                "member_id": 0.98,
                "provider_name": 0.95,
                "total_amount": 0.92,
                "service_date": 0.91
            },
            "warnings": []
        },
        "ncb_reference": "CLM-2024-567890",
        "ncb_submitted_at": "2024-12-18T10:43:00Z",
        "sheets_row_ref": "Sheet1!A142",
        "drive_file_id": "1abc123xyz",
        "retry_count": 0,
        "created_at": "2024-12-18T10:42:00Z",
        "updated_at": "2024-12-18T10:43:00Z"
    }
}
```

### POST /jobs/{job_id}/retry

Retry failed job.

**Request Body:** (optional)
```json
{
    "force": false,
    "reset_status": "pending"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "job_id": "job_abc123",
        "previous_status": "failed",
        "new_status": "pending",
        "message": "Job requeued for processing"
    }
}
```

---

## 4. Exceptions Endpoints

### GET /exceptions

List jobs in exception queue.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | int | 50 | Results per page |
| offset | int | 0 | Pagination offset |
| confidence_max | float | - | Max confidence score |

**Response:**
```json
{
    "success": true,
    "data": {
        "exceptions": [
            {
                "id": "job_def456",
                "email_id": "msg_uvw123",
                "sender": "john.doe@client.com",
                "received_at": "2024-12-18T10:42:00Z",
                "attachment_filename": "invoice.pdf",
                "extraction_result": {
                    "claim": {
                        "member_id": "M12345",
                        "member_name": "John Doe",
                        "provider_name": "Klinik Kesihatan",
                        "total_amount": null,
                        "raw_text": "..."
                    },
                    "confidence_score": 0.68,
                    "confidence_level": "low",
                    "warnings": [
                        "Amount field not detected",
                        "Low confidence on date extraction"
                    ]
                },
                "attachment_preview_url": "https://drive.google.com/...",
                "created_at": "2024-12-18T10:42:00Z"
            }
        ],
        "count": 4
    }
}
```

### POST /exceptions/{job_id}/approve

Approve exception with optional corrections.

**Request Body:**
```json
{
    "corrected_data": {
        "total_amount": 125.00,
        "service_date": "2024-12-15"
    },
    "reviewer_notes": "Manually verified amount from receipt"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "job_id": "job_def456",
        "status": "submitted",
        "ncb_reference": "CLM-2024-567891",
        "ncb_submitted_at": "2024-12-18T10:45:00Z"
    }
}
```

### POST /exceptions/{job_id}/reject

Reject exception.

**Request Body:**
```json
{
    "reason": "Unreadable receipt image",
    "action": "request_resubmission"
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "job_id": "job_def456",
        "status": "rejected",
        "reason": "Unreadable receipt image"
    }
}
```

---

## 5. Statistics Endpoints

### GET /stats/dashboard

Get dashboard statistics.

**Response:**
```json
{
    "success": true,
    "data": {
        "period": {
            "today": {
                "total_processed": 142,
                "successful": 138,
                "exceptions": 4,
                "failed": 0
            },
            "this_week": {
                "total_processed": 892,
                "successful": 865,
                "exceptions": 25,
                "failed": 2
            },
            "this_month": {
                "total_processed": 3421,
                "successful": 3298,
                "exceptions": 112,
                "failed": 11
            }
        },
        "rates": {
            "success_rate": 0.972,
            "exception_rate": 0.028,
            "ncb_submission_rate": 0.991
        },
        "performance": {
            "average_confidence": 0.938,
            "average_processing_time_seconds": 4.2,
            "average_submission_time_seconds": 0.8
        },
        "queue": {
            "pending_jobs": 3,
            "pending_exceptions": 4,
            "pending_submissions": 1
        },
        "last_updated": "2024-12-18T10:45:00Z"
    }
}
```

### GET /stats/daily

Get daily statistics.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| date | date | today | Date (YYYY-MM-DD) |

**Response:**
```json
{
    "success": true,
    "data": {
        "date": "2024-12-18",
        "summary": {
            "emails_received": 150,
            "attachments_processed": 168,
            "successful_extractions": 142,
            "exceptions": 4,
            "ncb_submissions": 138,
            "failures": 0
        },
        "hourly_breakdown": [
            {"hour": 0, "processed": 5},
            {"hour": 1, "processed": 3},
            ...
        ],
        "confidence_distribution": {
            "high": 128,
            "medium": 14,
            "low": 4
        },
        "top_providers": [
            {"name": "City Medical Centre", "count": 23},
            {"name": "Klinik Kesihatan Jaya", "count": 18}
        ]
    }
}
```

### GET /stats/trends

Get trend data over time.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| period | string | 7d | Time period (7d, 30d, 90d) |
| metric | string | all | Specific metric to retrieve |

**Response:**
```json
{
    "success": true,
    "data": {
        "period": "7d",
        "data_points": [
            {
                "date": "2024-12-12",
                "processed": 145,
                "success_rate": 0.965,
                "avg_confidence": 0.932
            },
            ...
        ]
    }
}
```

---

## 6. NCB API Integration (External)

> **Note:** This section documents the expected NCB API contract. Actual endpoint details TBD pending discovery session.

### POST /claims/submit

Submit extracted claim to NCB.

**Base URL:** `{NCB_API_BASE_URL}`

**Headers:**
```http
Authorization: Bearer {NCB_API_KEY}
Content-Type: application/json
X-Request-ID: {correlation_id}
```

**Request Body:**
```json
{
    "member_id": "M12345",
    "member_name": "John Doe",
    "provider": {
        "name": "City Medical Centre",
        "address": "123 Main St, Kuala Lumpur"
    },
    "service_date": "2024-12-15",
    "receipt_reference": "RCP-2024-001234",
    "amounts": {
        "total": 150.00,
        "currency": "MYR",
        "gst": null,
        "sst": 9.00,
        "items": [
            {"description": "Consultation", "amount": 80.00},
            {"description": "Medication", "amount": 70.00}
        ]
    },
    "source": {
        "email_id": "msg_xyz789",
        "filename": "receipt_001.jpg",
        "extraction_confidence": 0.94,
        "submitted_at": "2024-12-18T10:42:00Z"
    }
}
```

**Success Response (201):**
```json
{
    "success": true,
    "claim_reference": "CLM-2024-567890",
    "status": "received",
    "message": "Claim submitted successfully"
}
```

**Validation Error (400):**
```json
{
    "success": false,
    "error_code": "VALIDATION_FAILED",
    "message": "Invalid member ID",
    "details": {
        "field": "member_id",
        "reason": "Member not found in system"
    }
}
```

**Rate Limit (429):**
```json
{
    "success": false,
    "error_code": "RATE_LIMITED",
    "message": "Too many requests",
    "retry_after": 60
}
```

---

## 7. Gmail API Integration

### Required Scopes

```
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.modify
https://www.googleapis.com/auth/gmail.labels
```

### Message List Query

```
GET https://gmail.googleapis.com/gmail/v1/users/me/messages
?q=has:attachment is:unread -label:Claims/Processed
&maxResults=50
```

### Message Get

```
GET https://gmail.googleapis.com/gmail/v1/users/me/messages/{id}
?format=full
```

### Attachment Get

```
GET https://gmail.googleapis.com/gmail/v1/users/me/messages/{messageId}/attachments/{attachmentId}
```

### Modify Labels

```
POST https://gmail.googleapis.com/gmail/v1/users/me/messages/{id}/modify
{
    "addLabelIds": ["Claims/Processed"],
    "removeLabelIds": ["UNREAD"]
}
```

---

## 8. Google Sheets API Integration

### Append Row

```
POST https://sheets.googleapis.com/v4/spreadsheets/{spreadsheetId}/values/{range}:append
?valueInputOption=USER_ENTERED
{
    "values": [
        [
            "2024-12-18T10:42:00Z",
            "msg_xyz789",
            "john@client.com",
            "receipt_001.jpg",
            "M12345",
            "City Medical Centre",
            150.00,
            0.94,
            "submitted",
            "CLM-2024-567890",
            "2024-12-18T10:43:00Z",
            ""
        ]
    ]
}
```

### Update Cell

```
PUT https://sheets.googleapis.com/v4/spreadsheets/{spreadsheetId}/values/{range}
?valueInputOption=USER_ENTERED
{
    "values": [["CLM-2024-567890"]]
}
```

---

## 9. Google Drive API Integration

### Upload File

```
POST https://www.googleapis.com/upload/drive/v3/files
?uploadType=multipart

--boundary
Content-Type: application/json

{
    "name": "msg_xyz789_receipt_001.jpg",
    "parents": ["{folder_id}"],
    "properties": {
        "email_id": "msg_xyz789",
        "processed_at": "2024-12-18T10:42:00Z",
        "job_id": "job_abc123"
    }
}
--boundary
Content-Type: image/jpeg

{binary content}
--boundary--
```

### Create Folder

```
POST https://www.googleapis.com/drive/v3/files
{
    "name": "2024-12-18",
    "mimeType": "application/vnd.google-apps.folder",
    "parents": ["{parent_folder_id}"]
}
```

---

## 10. WebSocket Events (Admin Dashboard)

Connection: `ws://localhost:8080/ws`

### Event Types

**Job Status Update:**
```json
{
    "type": "job_status",
    "data": {
        "job_id": "job_abc123",
        "status": "submitted",
        "ncb_reference": "CLM-2024-567890",
        "timestamp": "2024-12-18T10:43:00Z"
    }
}
```

**New Exception:**
```json
{
    "type": "new_exception",
    "data": {
        "job_id": "job_def456",
        "filename": "invoice.pdf",
        "confidence_score": 0.68,
        "timestamp": "2024-12-18T10:42:00Z"
    }
}
```

**System Alert:**
```json
{
    "type": "system_alert",
    "data": {
        "severity": "warning",
        "component": "ncb_api",
        "message": "NCB API response time elevated",
        "timestamp": "2024-12-18T10:45:00Z"
    }
}
```

**Stats Update:**
```json
{
    "type": "stats_update",
    "data": {
        "processed_today": 143,
        "pending_exceptions": 4,
        "queue_size": 2,
        "timestamp": "2024-12-18T10:45:00Z"
    }
}
```

---

## 11. Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `VALIDATION_ERROR` | 400 | Request validation failed |
| `INVALID_JOB_ID` | 400 | Job ID format invalid |
| `JOB_NOT_FOUND` | 404 | Job does not exist |
| `UNAUTHORIZED` | 401 | Invalid or missing API key |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `RATE_LIMITED` | 429 | Too many requests |
| `NCB_UNAVAILABLE` | 503 | NCB API unreachable |
| `OCR_FAILED` | 500 | OCR processing error |
| `STORAGE_ERROR` | 500 | Google API error |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
