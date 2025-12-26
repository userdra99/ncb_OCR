# NCB API Quick Test Guide

**Purpose:** Quick reference for testing NCB API integration

---

## Environment Setup

### 1. Update .env File

```bash
# NCB API Configuration
NCB_API_BASE_URL=https://ncb.internal.company.com/api/v1
NCB_API_KEY=your-actual-ncb-api-key-here
NCB_TIMEOUT=30
NCB_MAX_RETRIES=3
```

### 2. Verify Network Access

```bash
# Test basic connectivity
curl -I https://ncb.internal.company.com/api/v1/health

# Expected: HTTP 200 OK (or 401 if auth required)
```

---

## Quick Tests

### Test 1: Health Check

```bash
curl -X GET https://ncb.internal.company.com/api/v1/health \
  -H "Authorization: Bearer ${NCB_API_KEY}" \
  -v
```

**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-12-24T10:00:00Z"
}
```

---

### Test 2: Single Valid Claim

```bash
curl -X POST https://ncb.internal.company.com/api/v1/claims/submit \
  -H "Authorization: Bearer ${NCB_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/ncb_single_valid_claim.json \
  -v
```

**Expected Response:**
```json
{
  "status": "success",
  "claim_reference": "CLM-2024-XXXXXX",
  "message": "Claim submitted successfully"
}
```

---

### Test 3: Invalid Claim (Missing Amount)

```bash
curl -X POST https://ncb.internal.company.com/api/v1/claims/submit \
  -H "Authorization: Bearer ${NCB_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "Event date": "2024-12-20",
    "Submission Date": "2024-12-24T17:00:00.000Z",
    "Invoice Number": "INV-TEST",
    "Policy Number": "POL-TEST"
  }' \
  -v
```

**Expected Response:** HTTP 400
```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "Missing required fields: Claim Amount"
}
```

---

### Test 4: Batch Claims

```bash
# Submit each claim from batch file
cat tests/fixtures/ncb_batch_claims.json | jq -c '.claims[]' | while read claim; do
  echo "Submitting claim..."
  echo "$claim" | curl -X POST https://ncb.internal.company.com/api/v1/claims/submit \
    -H "Authorization: Bearer ${NCB_API_KEY}" \
    -H "Content-Type: application/json" \
    -d @- \
    -s | jq .
  echo "---"
  sleep 1  # Rate limiting
done
```

---

## Run Automated Tests

### Full Integration Test Suite

```bash
# Run Python test script
python3 tests/integration/test_ncb_api.py
```

This will:
1. Test endpoint discovery
2. Validate JSON schemas
3. Run all 10 test cases
4. Generate detailed report

### Mock Service Tests

```bash
# Test with mock NCB API
python3 tests/integration/test_ncb_service_mock.py
```

This validates:
- Pydantic model configuration
- Field mapping (snake_case → NCB field names)
- Backward compatibility

---

## Common Issues & Solutions

### Issue 1: Connection Refused

**Symptom:**
```
curl: (7) Failed to connect to ncb.internal.company.com
```

**Solutions:**
1. Check VPN connection
2. Verify firewall rules
3. Confirm URL is correct
4. Contact NCB team for network access

---

### Issue 2: 401 Unauthorized

**Symptom:**
```json
{
  "status": "error",
  "message": "Unauthorized"
}
```

**Solutions:**
1. Verify `NCB_API_KEY` in .env
2. Check authorization header format: `Bearer <token>`
3. Request new API key from NCB team
4. Confirm API key has not expired

---

### Issue 3: 400 Validation Error

**Symptom:**
```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "..."
}
```

**Solutions:**
1. Check all required fields are present:
   - Event date
   - Submission Date
   - Claim Amount
   - Invoice Number
   - Policy Number
2. Verify date formats (ISO 8601)
3. Ensure `Claim Amount` > 0
4. Check event date is not in future

---

### Issue 4: 429 Rate Limited

**Symptom:**
```json
{
  "status": "error",
  "message": "Too many requests"
}
```

**Solutions:**
1. Check `Retry-After` header
2. Implement exponential backoff
3. Reduce submission rate
4. Use batch API if available

---

## Test Data Files

### Available Test Files

1. **ncb_test_data.json** - 10 comprehensive test cases
   - Valid claims: 7
   - Invalid claims: 2
   - Edge cases: 3

2. **ncb_single_valid_claim.json** - Quick validation
   - Amount: RM 435.50
   - Confidence: 98.85%

3. **ncb_batch_claims.json** - Batch processing
   - Claims: 5
   - Total: RM 3,941.00

---

## Field Requirements

### Required Fields (Must be present)

| Field | Format | Example |
|-------|--------|---------|
| Event date | ISO 8601 date | `"2024-12-20"` |
| Submission Date | ISO 8601 datetime | `"2024-12-24T10:30:00.000Z"` |
| Claim Amount | Positive float | `435.50` |
| Invoice Number | String | `"INV-2024-001234"` |
| Policy Number | String | `"POL-MYS-9876543"` |

### Optional Fields

| Field | Purpose |
|-------|---------|
| source_email_id | Internal tracking |
| source_filename | Internal tracking |
| extraction_confidence | OCR confidence (0.0-1.0) |

---

## Confidence Thresholds

| Range | Action | Review Required |
|-------|--------|-----------------|
| ≥ 90% | Auto-submit | No |
| 75-89% | Submit with flag | Yes |
| < 75% | Exception queue | N/A |

---

## Expected Response Times

| Operation | Target | Maximum |
|-----------|--------|---------|
| Single claim | < 500ms | 1000ms |
| Batch claim | < 3s | 5s |
| Health check | < 100ms | 500ms |

---

## Monitoring

### Check Circuit Breaker Status

```bash
curl -X GET http://localhost:8080/api/admin/health \
  -H "X-API-Key: ${ADMIN_API_KEY}"
```

### View Submission Queue

```bash
# Check Redis queue
redis-cli -u ${REDIS_URL} LLEN claims:submission_queue
```

### View Recent Logs

```bash
# Check application logs
docker-compose logs -f --tail=100 api
```

---

## Production Checklist

Before going live:

- [ ] NCB API credentials configured in .env
- [ ] Network access to NCB verified
- [ ] Health check passes
- [ ] Single claim test passes
- [ ] Batch test passes
- [ ] Circuit breaker tested
- [ ] Monitoring configured
- [ ] Error alerts configured
- [ ] Google Sheets audit log working
- [ ] Google Drive archive working

---

## Support Contacts

**NCB Integration Team:**
- Email: ncb-api-support@company.com
- Documentation: https://ncb.internal.company.com/api/docs

**Internal Support:**
- DevOps: devops@company.com
- API Issues: Check `/home/dra/projects/ncb_OCR/tests/reports/NCB_API_TEST_REPORT.md`

---

**Last Updated:** 2024-12-24
**Version:** 1.0.0
