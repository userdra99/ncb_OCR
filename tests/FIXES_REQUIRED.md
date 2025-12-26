# Required Fixes for Production Deployment

**Priority:** 🔴 Critical → 🟡 Medium → 🟢 Low
**Date:** 2025-12-26

---

## 🔴 Critical Fixes (Must Fix Before Production)

### 1. Email Watch Listener Event Loop Error

**File:** `src/workers/email_watch_listener.py`

**Current Problem:**
```
[error] Failed to process Pub/Sub message
[error] 'no running event loop'
```

**Root Cause:**
The Pub/Sub callback is trying to use async functions but is being called from a synchronous context.

**Fix:**
Find the Pub/Sub callback function and wrap async operations properly:

```python
# BEFORE (incorrect):
def pubsub_callback(message):
    await process_message(message)  # This fails

# AFTER (correct):
def pubsub_callback(message):
    asyncio.create_task(process_message_async(message))
    # OR
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(process_message_async(message))
    loop.close()
```

**Testing:**
```bash
# After fix, check logs for no more event loop errors
docker compose logs app --tail=100 | grep "event loop"
# Should show no errors
```

---

### 2. Unit Test AsyncMock Configuration

**File:** `tests/unit/test_queue_service.py`

**Current Problem:**
```
TypeError: object AsyncMock can't be used in 'await' expression
```

**Root Cause:**
AsyncMock is not properly configured to be awaitable.

**Fix:**

```python
# BEFORE (incorrect):
@pytest.fixture
async def mock_redis():
    mock = AsyncMock()
    return mock

# AFTER (correct):
@pytest.fixture
async def mock_redis():
    mock = AsyncMock()

    # Configure each async method
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.lpush = AsyncMock(return_value=1)
    mock.rpop = AsyncMock(return_value=None)
    mock.llen = AsyncMock(return_value=0)
    mock.hgetall = AsyncMock(return_value={})
    mock.hset = AsyncMock(return_value=True)
    mock.exists = AsyncMock(return_value=False)
    mock.setex = AsyncMock(return_value=True)

    return mock

# Also update the Redis connection mock:
@pytest.fixture
async def queue_service(mock_redis, mock_env):
    with patch('redis.asyncio.from_url') as mock_from_url:
        # Make from_url return the mock directly (not awaitable)
        mock_from_url.return_value = mock_redis

        service = QueueService()
        # Manually set redis to avoid connection
        service.redis = mock_redis
        yield service
```

**Testing:**
```bash
# After fix
docker compose exec app python -m pytest tests/unit/test_queue_service.py -v
# Should show 17 PASSED
```

---

## 🟡 Medium Priority Fixes

### 3. Health Check Redis Status

**File:** `src/api/routes/health.py` or `src/services/queue_service.py`

**Current Problem:**
Redis shows "not_initialized" but is actually working.

**Fix Option 1 - Eager initialization:**
```python
# In src/services/queue_service.py
class QueueService:
    def __init__(self):
        self.config = RedisConfig()
        self.redis = None
        # Add eager initialization
        asyncio.create_task(self.connect())
```

**Fix Option 2 - Health check triggers connection:**
```python
# In health endpoint
async def get_detailed_health():
    queue_service = QueueService()

    # Ensure connected before checking
    if queue_service.redis is None:
        await queue_service.connect()

    redis_status = "healthy" if queue_service.redis else "not_initialized"
```

**Fix Option 3 - Change status logic:**
```python
# More accurate status
async def get_redis_status():
    try:
        queue_service = QueueService()
        await queue_service.get_queue_size("test")
        return "healthy"
    except:
        return "unavailable"
```

---

### 4. API Key Documentation

**Files:**
- `.env.example`
- `README.md`
- `docs/API_CONTRACTS.md`

**Current Problem:**
Correct API key not documented. Tests show `ADMIN_API_KEY=dev_test_key_123456789` but it's rejected.

**Fix:**

1. Update `.env.example`:
```bash
# API Authentication
ADMIN_API_KEY=dev_test_key_123456789
# For production, use a secure random key:
# openssl rand -hex 32
```

2. Update `README.md`:
```markdown
### API Authentication

All API endpoints (except `/health`) require authentication via API key:

```bash
curl -H "X-API-Key: dev_test_key_123456789" \
  http://localhost:8080/api/stats
```

For production, generate a secure key:
```bash
openssl rand -hex 32
```
```

3. Check the auth middleware:
```python
# In src/api/middleware/auth.py
# Ensure it's reading from ADMIN_API_KEY env var
expected_key = os.getenv("ADMIN_API_KEY", "dev_test_key_123456789")
```

---

### 5. Enable GPU for OCR

**File:** `docker-compose.prod.yml`

**Current Status:**
OCR running in CPU mode (slower).

**Fix:**

```yaml
services:
  app:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

    environment:
      - OCR_USE_GPU=true
      - NVIDIA_VISIBLE_DEVICES=all
```

**Testing:**
```bash
# After rebuild
docker compose exec app python -c "
from src.services.ocr_service import OCRService
service = OCRService()
print(f'GPU enabled: {service.use_gpu}')
"
# Should show: GPU enabled: True
```

---

## 🟢 Low Priority Fixes

### 6. Test Output Directory

**File:** `scripts/e2e_test_workflow.py`

**Current Problem:**
Script tries to create `tests/output/` which is read-only in container.

**Fix:**

```python
# BEFORE:
output_dir = Path("tests/output")
output_dir.mkdir(exist_ok=True)

# AFTER:
output_dir = Path("/tmp/test_output")
output_dir.mkdir(exist_ok=True)
# OR use app data directory
output_dir = Path("/app/data/test_output")
output_dir.mkdir(exist_ok=True, parents=True)
```

---

### 7. Improve Code Coverage

**Files:** All `src/**/*.py`

**Current Coverage:** 11%
**Target:** >80%

**Recommended Approach:**

1. Fix existing unit tests (see Fix #2)
2. Add integration tests for:
   - OCR service with real images
   - Email service with mocked Gmail API
   - Sheets service with mocked Sheets API
   - NCB service with mocked NCB API

3. Run coverage:
```bash
docker compose exec app python -m pytest \
  tests/unit/ tests/integration/ \
  --cov=src \
  --cov-report=html \
  --cov-report=term-missing
```

---

## Quick Fix Summary

| Fix | Priority | Effort | Impact |
|-----|----------|--------|--------|
| Email watch event loop | 🔴 Critical | 1 hour | High |
| Unit test mocks | 🔴 Critical | 2 hours | Medium |
| Health check Redis | 🟡 Medium | 30 min | Low |
| API key docs | 🟡 Medium | 30 min | Medium |
| Enable GPU | 🟡 Medium | 1 hour | High |
| Test output dir | 🟢 Low | 10 min | Low |
| Code coverage | 🟢 Low | 4 hours | Medium |

**Total Critical Effort:** ~3 hours
**Total Medium Effort:** ~2 hours
**Total Low Effort:** ~4 hours

---

## Post-Fix Verification

After implementing fixes, run these commands to verify:

```bash
# 1. Check no event loop errors
docker compose logs app --tail=100 | grep -i "event loop"
# Should be empty

# 2. Run unit tests
docker compose exec app python -m pytest tests/unit/ -v
# Should show all PASSED

# 3. Check health
curl http://localhost:8080/health/detailed | jq .
# Redis should show "healthy"

# 4. Test API with key
curl -H "X-API-Key: dev_test_key_123456789" \
  http://localhost:8080/api/stats | jq .
# Should return stats, not "Invalid API key"

# 5. Check GPU (if enabled)
docker compose exec app python -c "
from src.services.ocr_service import OCRService
print(f'GPU: {OCRService().use_gpu}')
"
# Should show: GPU: True

# 6. Run full E2E test
docker compose exec app python /app/scripts/e2e_test_workflow.py
# Should complete without errors
```

---

## Pre-Production Checklist

After all fixes:

- [ ] All unit tests passing (17/17)
- [ ] No worker errors in logs
- [ ] Health check shows all components healthy
- [ ] API authentication working
- [ ] GPU enabled (if available)
- [ ] Test with real Gmail credentials
- [ ] Test with real Sheets/Drive
- [ ] Test NCB API submission (staging)
- [ ] Load testing (100+ concurrent jobs)
- [ ] Monitoring/alerting set up
- [ ] Documentation updated
- [ ] Runbook created

---

## Contact / Support

If you need help with any of these fixes:

1. Check the full test report: `tests/E2E_WORKFLOW_TEST_REPORT.md`
2. Review technical spec: `docs/TECHNICAL_SPEC.md`
3. Check PRD: `docs/PRD.md`
4. Review codebase: `CLAUDE.md` and `PROMPT.md`

---

**Last Updated:** 2025-12-26T01:48:00Z
