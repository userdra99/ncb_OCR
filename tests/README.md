# Test Suite - Claims Data Entry Agent

Comprehensive test suite covering unit, integration, and end-to-end tests.

## Quick Start

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run specific test types
pytest -m unit          # Unit tests only (fast)
pytest -m integration   # Integration tests
pytest -m e2e           # End-to-end tests (slow)

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific service tests
pytest tests/unit/test_ocr_service.py -v
```

## Test Organization

```
tests/
├── unit/                    # Unit tests (isolated, mocked dependencies)
│   ├── test_ocr_service.py
│   ├── test_email_service.py
│   ├── test_ncb_service.py
│   ├── test_queue_service.py
│   ├── test_sheets_service.py
│   └── test_drive_service.py
├── integration/             # Integration tests (multiple components)
│   └── test_workers.py
├── e2e/                     # End-to-end tests (full pipeline)
│   └── test_claim_pipeline.py
├── fixtures/                # Test data and mock fixtures
│   ├── images/
│   ├── emails/
│   └── expected/
├── conftest.py              # Pytest configuration and shared fixtures
└── pytest.ini               # Pytest settings
```

## Test Categories

### Unit Tests (Fast, ~200 tests)

Test individual components in isolation with mocked dependencies.

**Coverage:**
- OCR Service: Text extraction, data structuring, confidence calculation
- Email Service: Gmail polling, attachment downloading, email processing
- NCB Service: API submission, error handling, retry logic
- Queue Service: Job management, deduplication, status updates
- Sheets Service: Logging, audit trail, daily summaries
- Drive Service: File archiving, folder creation, metadata

**Markers:**
- `@pytest.mark.unit`
- `@pytest.mark.ocr`, `@pytest.mark.gmail`, `@pytest.mark.ncb`, etc.

### Integration Tests (Medium, ~30 tests)

Test interaction between multiple components.

**Coverage:**
- Email Poller Worker: End-to-end email processing
- OCR Processor Worker: Complete OCR pipeline
- NCB Submitter Worker: Submission with retries
- Worker coordination and error propagation

**Markers:**
- `@pytest.mark.integration`
- `@pytest.mark.worker`

### End-to-End Tests (Slow, ~15 tests)

Test complete workflows from email to NCB submission.

**Coverage:**
- High-confidence auto-submission flow
- Low-confidence exception routing
- Medium-confidence review flagging
- Malaysian receipt format handling
- Duplicate detection
- Error recovery and fallback
- Performance benchmarks

**Markers:**
- `@pytest.mark.e2e`
- `@pytest.mark.slow`
- `@pytest.mark.confidence`
- `@pytest.mark.malaysian`

## Test Configuration

### pytest.ini

```ini
[pytest]
# Coverage thresholds
--cov-fail-under=80

# Markers for test selection
markers =
    unit: Unit tests (fast)
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
    ocr: OCR service tests
    confidence: Confidence threshold tests
    malaysian: Malaysian receipt format tests
```

### Environment Variables

Tests use `.env.example` values by default. Override for specific test scenarios:

```bash
# Use test database
export REDIS_URL=redis://localhost:6379/1

# Disable GPU for CI
export OCR_USE_GPU=false

# Run tests
pytest
```

## Coverage Requirements

| Component | Target Coverage | Current |
|-----------|----------------|---------|
| OCR Service | >85% | TBD |
| Email Service | >80% | TBD |
| NCB Service | >80% | TBD |
| Queue Service | >80% | TBD |
| Workers | >75% | TBD |
| Overall | >80% | TBD |

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Fast Tests Only

```bash
pytest -m "unit and not slow"
```

### Run Tests for Specific Service

```bash
pytest tests/unit/test_ocr_service.py -v
```

### Run with Coverage Report

```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Run Specific Test

```bash
pytest tests/unit/test_ocr_service.py::TestOCRService::test_extract_text_from_image -v
```

### Run in Parallel (faster)

```bash
pytest -n auto
```

### Run with Live Logging

```bash
pytest -v --log-cli-level=DEBUG
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Run tests
        run: |
          pytest --cov=src --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Writing New Tests

### Test Structure (AAA Pattern)

```python
@pytest.mark.unit
@pytest.mark.ocr
async def test_extract_text_from_image(ocr_service, test_data_dir):
    """
    Test OCR text extraction

    Given: A receipt image file
    When: extract_text() is called
    Then: Text blocks are returned with confidence scores
    """
    # Arrange
    test_image = test_data_dir / "sample_receipt.jpg"

    # Act
    result = await ocr_service.extract_text(test_image)

    # Assert
    assert result is not None
    assert len(result.text_blocks) > 0
    assert all(block.confidence > 0.5 for block in result.text_blocks)
```

### Using Fixtures

Shared fixtures are defined in `conftest.py`:

```python
def test_with_mock_redis(mock_redis):
    # mock_redis is automatically available
    mock_redis.get.return_value = "test_value"
```

### Async Tests

Use `@pytest.mark.asyncio` for async tests:

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_operation()
    assert result is not None
```

## Test Data

Test fixtures are in `tests/fixtures/`:

- **images/**: Sample receipt images (various formats, quality levels)
- **emails/**: Mock email metadata
- **expected/**: Expected extraction results

See `tests/fixtures/README.md` for details.

## Mocking Best Practices

1. **Mock external dependencies**: Gmail API, NCB API, Google Services
2. **Don't mock the code under test**: Test actual implementation
3. **Use realistic test data**: Based on actual Malaysian receipts
4. **Test error paths**: Network failures, API errors, edge cases

## Debugging Tests

### Run with debugger

```bash
pytest --pdb
```

### Print output during tests

```bash
pytest -s
```

### Verbose output

```bash
pytest -vv
```

### Show local variables on failure

```bash
pytest -l
```

## Performance Testing

Performance benchmarks are in E2E tests:

```python
@pytest.mark.e2e
@pytest.mark.slow
async def test_performance_100_claims_under_10_minutes():
    # Process 100 claims and measure time
    pass
```

Run performance tests:

```bash
pytest -m "e2e and slow" --durations=0
```

## Known Issues

- OCR tests require sample images (add to `tests/fixtures/images/`)
- Integration tests require Redis running
- E2E tests are slow (~2-5 minutes total)

## Contributing

When adding new features:

1. Write tests first (TDD)
2. Ensure >80% coverage
3. Add appropriate markers
4. Update this README if adding new test categories
5. Run full test suite before committing:
   ```bash
   pytest --cov=src --cov-fail-under=80
   ```

## Questions?

See:
- `conftest.py` for available fixtures
- `pytest.ini` for configuration options
- Individual test files for examples
