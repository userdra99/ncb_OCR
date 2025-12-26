# Quick Fix Guide - Test Suite Recovery

**Last Updated:** December 26, 2025
**Priority:** 🔴 Critical
**Status:** 24.7% tests passing (37/150), 24% coverage
**Goal:** Get to 90%+ passing (135/150), 80% coverage
**Estimated Time:** 12-18 hours to green, 40-60 hours to 80% coverage

---

## Priority 1: Fix Service Initialization (Day 1-2)

### Problem
29 tests failing with: `TypeError: Service.__init__() takes 1 positional argument but 2 were given`

### Affected Files
- `tests/unit/test_drive_service.py` (7 tests)
- `tests/unit/test_email_service.py` (15 tests)
- `tests/unit/test_sheets_service.py` (likely 7 tests)

### Root Cause
Services refactored from:
```python
# OLD
service = DriveService(credentials_path="/path/to/creds.json")
```
To:
```python
# NEW
class DriveService:
    def __init__(self):
        self.config = settings.drive  # Loads internally
```

### Fix
**File:** `tests/conftest.py`

```python
# BEFORE (broken)
@pytest.fixture
def drive_service(tmp_path):
    creds_path = tmp_path / "fake_creds.json"
    creds_path.write_text('{"type": "service_account"}')
    return DriveService(credentials_path=str(creds_path))

# AFTER (working)
@pytest.fixture
def drive_service(monkeypatch):
    # Mock settings instead of passing credentials
    monkeypatch.setattr(
        "src.services.drive_service.settings.drive",
        DriveSettings(folder_id="test-folder-123")
    )
    return DriveService()  # No arguments
```

**Apply to:**
- `drive_service` fixture
- `email_service` fixture
- `sheets_service` fixture

---

## Priority 2: Add HTTP Mocks for NCB Tests (Day 2-3)

### Problem
20 tests failing with: `tenacity.RetryError: NCBConnectionError`

### Affected File
- `tests/unit/test_ncb_service.py` (20 tests)

### Root Cause
Tests making real HTTP requests, retry logic activating with long delays.

### Fix
Install respx:
```bash
pip install respx
```

**Update tests:**
```python
import respx
import httpx

@pytest.mark.asyncio
async def test_submit_claim_success(respx_mock):
    # Mock the NCB API endpoint
    respx_mock.post("https://ncb-api.example.com/api/v1/claims").mock(
        return_value=httpx.Response(
            200,
            json={
                "claim_id": "CLM-2024-001",
                "status": "accepted",
                "reference": "NCB123456"
            }
        )
    )

    service = NCBService()
    claim = NCBSubmissionRequest(...)

    result = await service.submit_claim(claim)

    assert result.claim_id == "CLM-2024-001"
    assert result.status == "accepted"
```

**Mock all endpoints:**
- POST `/claims` - Submit claim
- GET `/claims/{id}` - Get status
- GET `/health` - Health check

---

## Priority 3: Add Test Timeouts (Day 3)

### Problem
Test suite hangs indefinitely on slow tests.

### Fix
Install pytest-timeout:
```bash
pip install pytest-timeout
```

**Update:** `pyproject.toml`
```toml
[tool.pytest.ini_options]
timeout = 30
timeout_method = "thread"
addopts = [
    "-v",
    "--cov=src",
    "--cov-report=html",
    "--cov-report=term-missing",
    "--timeout=30"
]
```

**For specific slow tests:**
```python
@pytest.mark.timeout(60)  # Allow 60s for this test
async def test_performance_100_claims():
    ...
```

---

## Priority 4: Mock Retry Delays (Day 3)

### Problem
NCB tests with tenacity retry take 10-20 seconds each.

### Fix
```python
from unittest.mock import patch
import tenacity

@patch('tenacity.wait_exponential')
async def test_submit_claim_retries(mock_wait):
    # Make retries instant
    mock_wait.return_value = tenacity.wait_none()

    # Test logic...
```

Or patch globally in conftest.py:
```python
@pytest.fixture(autouse=True)
def fast_retries():
    with patch('tenacity.wait_exponential', return_value=tenacity.wait_none()):
        yield
```

---

## Priority 5: Enable Parallel Testing (Day 4)

### Problem
Tests run serially, taking 180+ seconds.

### Fix
Install pytest-xdist:
```bash
pip install pytest-xdist
```

**Run tests in parallel:**
```bash
pytest -n auto  # Auto-detect CPU cores
pytest -n 4     # Use 4 workers
```

**Update pyproject.toml:**
```toml
[tool.pytest.ini_options]
addopts = [
    "-n", "auto",
    "-v",
    "--cov=src"
]
```

**Expected speedup:** 3-4x faster (180s → 45-60s)

---

## Priority 6: Increase Coverage (Week 2)

### Zero Coverage Modules to Fix

| Module | Lines | Priority | Estimated Time |
|--------|-------|----------|----------------|
| `workers/email_poller.py` | 88 | HIGH | 2h |
| `workers/ncb_submitter.py` | 84 | HIGH | 2h |
| `workers/ocr_processor.py` | 98 | HIGH | 2h |
| `api/routes/jobs.py` | 86 | MEDIUM | 1.5h |
| `api/routes/stats.py` | 98 | MEDIUM | 1.5h |
| `services/email_service.py` | 120 | HIGH | 3h |
| `services/sheets_service.py` | 66 | MEDIUM | 2h |

**Total:** ~14 hours to reach 80% coverage

### Strategy
1. **Workers (270 lines)** - Focus here first
   - Create `tests/unit/test_workers.py` (separate from integration)
   - Mock Redis queue operations
   - Mock service dependencies

2. **API Routes (364 lines)** - Test endpoints
   - Use FastAPI TestClient
   - Mock service layer
   - Test error responses

3. **Services** - Complete existing test files
   - Fix initialization
   - Add edge cases
   - Test error handling

---

## Quick Commands

### Run All Tests
```bash
docker exec claims-app /home/appuser/.local/bin/pytest /app/tests/ -v
```

### Run Specific Suite
```bash
# E2E only (these work!)
docker exec claims-app /home/appuser/.local/bin/pytest /app/tests/e2e/ -v

# NCB service only
docker exec claims-app /home/appuser/.local/bin/pytest /app/tests/unit/test_ncb_service.py -v

# With coverage
docker exec claims-app /home/appuser/.local/bin/pytest /app/tests/ --cov=src --cov-report=html
```

### View Coverage
```bash
# Copy report from container
docker cp claims-app:/app/htmlcov /home/dra/projects/ncb_OCR/

# Open in browser
xdg-open /home/dra/projects/ncb_OCR/htmlcov/index.html
```

### Kill Hanging Tests
```bash
docker exec claims-app pkill -9 pytest
```

---

## Validation Checklist

After fixes, verify:

- [ ] All 120 tests collected successfully
- [ ] E2E tests: 17/17 passing (already ✅)
- [ ] Integration tests: 12/12 passing (currently 11/12)
- [ ] Unit tests - Drive: 7/7 passing (currently 0/7)
- [ ] Unit tests - Email: 15/15 passing (currently 0/15)
- [ ] Unit tests - NCB: 25/25 passing (currently 5/25)
- [ ] Unit tests - Sheets: 7/7 passing (not yet run)
- [ ] Unit tests - OCR: passing (not yet run)
- [ ] Unit tests - Queue: passing (not yet run)
- [ ] Coverage ≥ 80% (currently 14%)
- [ ] Test suite completes in < 60s (currently 180s+)

---

## Success Criteria

**Phase 1 Complete (Week 1):**
- ✅ All 120 tests run to completion
- ✅ 95%+ pass rate
- ✅ Test suite completes in < 60s
- ✅ No test hangs/timeouts

**Phase 2 Complete (Week 2):**
- ✅ Code coverage ≥ 80%
- ✅ All critical paths tested
- ✅ Worker tests implemented

**Phase 3 Complete (Week 3):**
- ✅ No deprecation warnings
- ✅ CI/CD pipeline integrated
- ✅ Documentation updated

---

## Help & Resources

**View Full Report:**
```bash
cat /home/dra/projects/ncb_OCR/tests/TEST_EXECUTION_REPORT.md
```

**Coverage Report:**
```bash
xdg-open /home/dra/projects/ncb_OCR/htmlcov/index.html
```

**Pytest Docs:**
- Fixtures: https://docs.pytest.org/en/stable/fixture.html
- Mocking: https://docs.pytest.org/en/stable/how-to/monkeypatch.html
- Async: https://github.com/pytest-dev/pytest-asyncio

**Respx (HTTP mocking):**
- https://lundberg.github.io/respx/

**Pytest Timeout:**
- https://github.com/pytest-dev/pytest-timeout
