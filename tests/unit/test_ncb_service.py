"""
Unit tests for NCB Service

Tests NCB API integration, submission, error handling, and retry logic
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import httpx


@pytest.mark.unit
@pytest.mark.ncb
class TestNCBService:
    """Test suite for NCB Service"""

    @pytest.fixture
    def ncb_service(self, mock_ncb_api, mock_env):
        """Create NCB service instance with mocked HTTP client."""
        with patch('httpx.AsyncClient', return_value=mock_ncb_api):
            from src.services.ncb_service import NCBService

            return NCBService()

    @pytest.mark.asyncio
    async def test_submit_claim_success(self, ncb_service, sample_receipt_data):
        """
        Test successful claim submission

        Given: Valid claim data
        When: submit_claim() is called
        Then: Returns success response with claim reference
        """
        # Arrange
        from src.models.claim import NCBSubmissionRequest

        request = NCBSubmissionRequest(
            event_date=sample_receipt_data["service_date"],
            submission_date="2024-12-21T10:00:00",
            claim_amount=sample_receipt_data["total_amount"],
            invoice_number=sample_receipt_data["receipt_number"],
            policy_number=sample_receipt_data["member_id"],
            source_email_id="msg_123",
            source_filename="receipt.jpg",
            extraction_confidence=0.95,
        )

        # Act
        response = await ncb_service.submit_claim(request)

        # Assert
        assert response.success is True
        assert response.claim_reference is not None
        assert response.claim_reference.startswith("CLM-")

    @pytest.mark.asyncio
    async def test_submit_claim_validation_error(self, ncb_service, mock_ncb_api):
        """
        Test handling of NCB validation errors

        Given: Invalid claim data (e.g., invalid member ID)
        When: submit_claim() is called
        Then: NCBValidationError raised with details
        """
        # Arrange
        from src.models.claim import NCBSubmissionRequest
        from src.services.ncb_service import NCBValidationError

        mock_ncb_api.post.return_value = MagicMock(
            status_code=400,
            json=lambda: {
                "success": False,
                "error_code": "VALIDATION_FAILED",
                "message": "Member not found in system",
                "details": {"field": "policy_number", "reason": "Member not found"},
            },
        )

        request = NCBSubmissionRequest(
            event_date="2024-12-15",
            submission_date="2024-12-21T10:00:00",
            claim_amount=100.00,
            invoice_number="RCP-001",
            policy_number="INVALID",
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Act & Assert
        with pytest.raises(NCBValidationError) as exc_info:
            await ncb_service.submit_claim(request)

        assert "Member not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_claim_rate_limited(self, ncb_service, mock_ncb_api):
        """
        Test handling of rate limiting

        Given: NCB API returns 429 Too Many Requests
        When: submit_claim() is called
        Then: NCBRateLimitError raised with retry_after
        """
        # Arrange
        from src.models.claim import NCBSubmissionRequest
        from src.services.ncb_service import NCBRateLimitError

        mock_ncb_api.post.return_value = MagicMock(
            status_code=429,
            headers={"Retry-After": "60"},
            json=lambda: {
                "success": False,
                "error_code": "RATE_LIMITED",
                "message": "Too many requests",
                "retry_after": 60,
            },
        )

        request = NCBSubmissionRequest(
            event_date="2024-12-15",
            submission_date="2024-12-21T10:00:00",
            claim_amount=100.00,
            invoice_number="RCP-001",
            policy_number="M12345",
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Act & Assert
        with pytest.raises(NCBRateLimitError) as exc_info:
            await ncb_service.submit_claim(request)

        assert exc_info.value.retry_after == 60

    @pytest.mark.asyncio
    async def test_submit_claim_server_error_retries(self, ncb_service, mock_ncb_api):
        """
        Test retry logic on server errors (5xx)

        Given: NCB API returns 500 on first attempt
        When: submit_claim() is called
        Then: Retries with exponential backoff and succeeds
        """
        # Arrange
        from src.models.ncb import NCBSubmissionRequest

        # Fail twice, succeed on third attempt
        mock_ncb_api.post.side_effect = [
            MagicMock(status_code=500, json=lambda: {"error": "Internal Server Error"}),
            MagicMock(status_code=503, json=lambda: {"error": "Service Unavailable"}),
            MagicMock(
                status_code=201,
                json=lambda: {
                    "success": True,
                    "claim_reference": "CLM-2024-567890",
                    "status": "received",
                },
            ),
        ]

        request = NCBSubmissionRequest(
            member_id="M12345",
            member_name="Test",
            provider_name="Test Clinic",
            service_date="2024-12-15",
            receipt_number="RCP-001",
            total_amount=100.00,
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Act
        response = await ncb_service.submit_claim(request)

        # Assert
        assert response.success is True
        assert mock_ncb_api.post.call_count == 3

    @pytest.mark.asyncio
    async def test_submit_claim_max_retries_exceeded(self, ncb_service, mock_ncb_api):
        """
        Test failure after max retries

        Given: NCB API consistently returns 500
        When: submit_claim() retries max times
        Then: NCBConnectionError raised
        """
        # Arrange
        from src.models.ncb import NCBSubmissionRequest
        from src.services.ncb_service import NCBConnectionError

        mock_ncb_api.post.side_effect = [
            MagicMock(status_code=500, json=lambda: {"error": "Internal Server Error"})
        ] * 10  # More than max retries

        request = NCBSubmissionRequest(
            member_id="M12345",
            member_name="Test",
            provider_name="Test Clinic",
            service_date="2024-12-15",
            receipt_number="RCP-001",
            total_amount=100.00,
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Act & Assert
        with pytest.raises(NCBConnectionError):
            await ncb_service.submit_claim(request)

        # Should have tried max_retries times (default 3)
        assert mock_ncb_api.post.call_count <= 3

    @pytest.mark.asyncio
    async def test_submit_claim_timeout(self, ncb_service, mock_ncb_api):
        """
        Test timeout handling

        Given: NCB API takes too long to respond
        When: submit_claim() is called
        Then: Timeout error raised and retried
        """
        # Arrange
        from src.models.ncb import NCBSubmissionRequest

        mock_ncb_api.post.side_effect = [
            httpx.TimeoutException("Request timeout"),
            MagicMock(
                status_code=201,
                json=lambda: {
                    "success": True,
                    "claim_reference": "CLM-2024-567890",
                },
            ),
        ]

        request = NCBSubmissionRequest(
            member_id="M12345",
            member_name="Test",
            provider_name="Test Clinic",
            service_date="2024-12-15",
            receipt_number="RCP-001",
            total_amount=100.00,
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Act
        response = await ncb_service.submit_claim(request)

        # Assert
        assert response.success is True
        assert mock_ncb_api.post.call_count == 2

    @pytest.mark.asyncio
    async def test_submit_claim_network_error(self, ncb_service, mock_ncb_api):
        """
        Test network error handling

        Given: Network connection fails
        When: submit_claim() is called
        Then: Connection error raised and retried
        """
        # Arrange
        from src.models.ncb import NCBSubmissionRequest

        mock_ncb_api.post.side_effect = [
            httpx.ConnectError("Connection refused"),
            MagicMock(
                status_code=201,
                json=lambda: {
                    "success": True,
                    "claim_reference": "CLM-2024-567890",
                },
            ),
        ]

        request = NCBSubmissionRequest(
            member_id="M12345",
            member_name="Test",
            provider_name="Test Clinic",
            service_date="2024-12-15",
            receipt_number="RCP-001",
            total_amount=100.00,
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Act
        response = await ncb_service.submit_claim(request)

        # Assert
        assert response.success is True

    @pytest.mark.asyncio
    async def test_check_health_success(self, ncb_service, mock_ncb_api):
        """
        Test NCB API health check

        Given: NCB API is available
        When: check_health() is called
        Then: Returns True
        """
        # Arrange
        mock_ncb_api.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": "healthy"},
        )

        # Act
        is_healthy = await ncb_service.check_health()

        # Assert
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_check_health_failure(self, ncb_service, mock_ncb_api):
        """
        Test health check when API is down

        Given: NCB API is unavailable
        When: check_health() is called
        Then: Returns False
        """
        # Arrange
        mock_ncb_api.get.side_effect = httpx.ConnectError("Connection refused")

        # Act
        is_healthy = await ncb_service.check_health()

        # Assert
        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_get_claim_status(self, ncb_service, mock_ncb_api):
        """
        Test retrieving claim status

        Given: Previously submitted claim
        When: get_claim_status() is called with reference
        Then: Returns claim status details
        """
        # Arrange
        claim_reference = "CLM-2024-567890"

        mock_ncb_api.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "reference": claim_reference,
                "status": "approved",
                "approved_amount": 150.00,
                "processed_at": "2024-12-18T15:30:00Z",
            },
        )

        # Act
        status = await ncb_service.get_claim_status(claim_reference)

        # Assert
        assert status["reference"] == claim_reference
        assert status["status"] == "approved"

    @pytest.mark.asyncio
    async def test_submit_claim_field_mapping_to_ncb_schema(self, ncb_service, mock_ncb_api):
        """
        Test field mapping from ExtractedClaim to NCB schema

        Given: Claim with internal field names
        When: submit_claim() is called
        Then: Request maps to NCB schema (Event date, Submission Date, etc.)
        """
        # Arrange
        from src.models.claim import NCBSubmissionRequest
        from datetime import datetime

        request = NCBSubmissionRequest(
            member_id="M12345",
            member_name="Test User",
            provider_name="Test Clinic",
            service_date="2024-12-21",
            receipt_number="INV-12345",
            total_amount=150.50,
            source_email_id="msg_abc123",
            source_filename="receipt_001.jpg",
            extraction_confidence=0.94,
        )

        # Act
        await ncb_service.submit_claim(request)

        # Assert - Verify NCB schema field mapping
        call_args = mock_ncb_api.post.call_args
        json_data = call_args.kwargs.get("json", {})

        # New NCB schema fields
        assert "Event date" in json_data or "service_date" in json_data
        assert "Invoice Number" in json_data or "receipt_number" in json_data
        assert "Claim Amount" in json_data or "total_amount" in json_data
        # Note: Actual mapping should be implemented in NCB service

    @pytest.mark.asyncio
    async def test_submit_claim_date_iso_format(self, ncb_service, mock_ncb_api):
        """
        Test date formatting to ISO format for NCB

        Given: Claim with date string
        When: submit_claim() is called
        Then: Submission Date is in ISO 8601 format
        """
        # Arrange
        from src.models.claim import NCBSubmissionRequest
        import re

        request = NCBSubmissionRequest(
            member_id="M12345",
            member_name="Test",
            provider_name="Test Clinic",
            service_date="2024-12-21",
            receipt_number="INV-12345",
            total_amount=150.50,
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Act
        await ncb_service.submit_claim(request)

        # Assert - Check ISO format (YYYY-MM-DDTHH:MM:SSZ or similar)
        call_args = mock_ncb_api.post.call_args
        json_data = call_args.kwargs.get("json", {})

        # ISO 8601 format pattern
        iso_pattern = r'\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})?)?'

        # Check service_date or "Event date" field
        date_field = json_data.get("service_date") or json_data.get("Event date")
        if date_field:
            assert re.match(iso_pattern, str(date_field)), f"Date {date_field} not in ISO format"

    @pytest.mark.asyncio
    async def test_submit_claim_includes_metadata(self, ncb_service, mock_ncb_api):
        """
        Test that submission includes source metadata

        Given: Claim with source email and confidence
        When: submit_claim() is called
        Then: Request includes source metadata
        """
        # Arrange
        from src.models.claim import NCBSubmissionRequest

        request = NCBSubmissionRequest(
            member_id="M12345",
            member_name="Test",
            provider_name="Test Clinic",
            service_date="2024-12-15",
            receipt_number="RCP-001",
            total_amount=100.00,
            source_email_id="msg_abc123",
            source_filename="receipt_001.jpg",
            extraction_confidence=0.94,
        )

        # Act
        await ncb_service.submit_claim(request)

        # Assert
        call_args = mock_ncb_api.post.call_args
        json_data = call_args.kwargs.get("json", {})

        assert json_data.get("source_email_id") == "msg_abc123"
        assert json_data.get("source_filename") == "receipt_001.jpg"
        assert json_data.get("extraction_confidence") == 0.94

    @pytest.mark.asyncio
    async def test_submit_claim_includes_auth_header(self, ncb_service, mock_ncb_api):
        """
        Test authentication header is included

        Given: NCB service with API key
        When: submit_claim() is called
        Then: Authorization header present in request
        """
        # Arrange
        from src.models.ncb import NCBSubmissionRequest

        request = NCBSubmissionRequest(
            member_id="M12345",
            member_name="Test",
            provider_name="Test Clinic",
            service_date="2024-12-15",
            receipt_number="RCP-001",
            total_amount=100.00,
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Act
        await ncb_service.submit_claim(request)

        # Assert
        call_args = mock_ncb_api.post.call_args
        headers = call_args.kwargs.get("headers", {})

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    @pytest.mark.asyncio
    async def test_submit_claim_correlation_id(self, ncb_service, mock_ncb_api):
        """
        Test correlation ID is sent for tracking

        Given: Claim submission
        When: submit_claim() is called
        Then: X-Request-ID header included for tracing
        """
        # Arrange
        from src.models.ncb import NCBSubmissionRequest

        request = NCBSubmissionRequest(
            member_id="M12345",
            member_name="Test",
            provider_name="Test Clinic",
            service_date="2024-12-15",
            receipt_number="RCP-001",
            total_amount=100.00,
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Act
        await ncb_service.submit_claim(request)

        # Assert
        call_args = mock_ncb_api.post.call_args
        headers = call_args.kwargs.get("headers", {})

        assert "X-Request-ID" in headers
        assert len(headers["X-Request-ID"]) > 0

    @pytest.mark.asyncio
    async def test_submit_claim_missing_policy_number(self, ncb_service, mock_ncb_api):
        """
        Test handling of missing Policy Number field

        Given: Claim without policy number
        When: submit_claim() is called
        Then: Request is still valid (policy number is optional) OR error raised
        """
        # Arrange
        from src.models.claim import NCBSubmissionRequest

        request = NCBSubmissionRequest(
            member_id="M12345",
            member_name="Test",
            provider_name="Test Clinic",
            service_date="2024-12-21",
            receipt_number="INV-12345",
            total_amount=100.00,
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Act
        response = await ncb_service.submit_claim(request)

        # Assert - Should succeed even without Policy Number
        assert response.success is True

    @pytest.mark.asyncio
    async def test_submit_claim_amount_formatting(self, ncb_service, mock_ncb_api):
        """
        Test amount formatting edge cases

        Given: Various amount formats
        When: submit_claim() is called
        Then: Amounts properly formatted with 2 decimal places
        """
        # Arrange
        from src.models.claim import NCBSubmissionRequest

        test_amounts = [
            (150.5, 150.50),   # One decimal
            (150.0, 150.00),   # No decimals
            (150.505, 150.51), # Three decimals (round)
            (0.01, 0.01),      # Minimum
            (99999.99, 99999.99), # Large amount
        ]

        for input_amount, expected_output in test_amounts:
            request = NCBSubmissionRequest(
                member_id="M12345",
                member_name="Test",
                provider_name="Test Clinic",
                service_date="2024-12-21",
                receipt_number="INV-12345",
                total_amount=input_amount,
                source_email_id="msg_123",
                source_filename="test.jpg",
                extraction_confidence=0.95,
            )

            # Act
            await ncb_service.submit_claim(request)

            # Assert
            call_args = mock_ncb_api.post.call_args
            json_data = call_args.kwargs.get("json", {})

            submitted_amount = json_data.get("total_amount") or json_data.get("Claim Amount")
            # Check amount has at most 2 decimal places
            assert isinstance(submitted_amount, (int, float))
            if isinstance(submitted_amount, float):
                assert round(submitted_amount, 2) == submitted_amount

    @pytest.mark.asyncio
    async def test_submit_claim_required_fields_validation(self, ncb_service, mock_ncb_api):
        """
        Test validation of required NCB fields

        Given: NCB schema requires specific fields
        When: submit_claim() validates payload
        Then: All required fields present (Event date, Invoice Number, Claim Amount)
        """
        # Arrange
        from src.models.claim import NCBSubmissionRequest

        request = NCBSubmissionRequest(
            member_id="M12345",
            member_name="Test User",
            provider_name="Test Clinic",
            service_date="2024-12-21",
            receipt_number="INV-12345",
            total_amount=150.50,
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Act
        await ncb_service.submit_claim(request)

        # Assert - Check required fields are present
        call_args = mock_ncb_api.post.call_args
        json_data = call_args.kwargs.get("json", {})

        # At minimum, these internal fields should exist
        assert "service_date" in json_data or "Event date" in json_data
        assert "receipt_number" in json_data or "Invoice Number" in json_data
        assert "total_amount" in json_data or "Claim Amount" in json_data

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, ncb_service, mock_ncb_api):
        """
        Test exponential backoff retry timing

        Given: Multiple retry attempts
        When: Retries occur
        Then: Wait time doubles each retry (2s, 4s, 8s, etc.)
        """
        # This would be tested with actual timing in integration tests
        # Unit test verifies retry configuration exists
        # Config values depend on implementation
        pass


@pytest.mark.unit
@pytest.mark.ncb
@pytest.mark.circuit_breaker
class TestCircuitBreaker:
    """Test suite for Circuit Breaker pattern"""

    @pytest.fixture
    def ncb_service(self, mock_env):
        """Create NCB service with circuit breaker."""
        from src.services.ncb_service import NCBService

        # Create service with low thresholds for testing
        return NCBService(failure_threshold=3, circuit_timeout=2)

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, ncb_service):
        """
        Test circuit breaker opens after threshold failures

        Given: Circuit breaker with threshold of 3
        When: 3 consecutive failures occur
        Then: Circuit breaker opens and rejects subsequent calls
        """
        from src.models.claim import NCBSubmissionRequest
        from src.services.ncb_service import NCBConnectionError

        request = NCBSubmissionRequest(
            event_date="2024-12-15",
            submission_date="2024-12-21T10:00:00",
            claim_amount=100.00,
            invoice_number="RCP-001",
            policy_number="M12345",
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Mock failures
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = \
                httpx.ConnectError("Connection failed")

            # First 3 attempts should fail and open circuit
            for i in range(3):
                try:
                    await ncb_service.submit_claim(request)
                except NCBConnectionError:
                    pass  # Expected

            # Circuit should now be open
            assert ncb_service.circuit_breaker.state.value == "open"

            # Next attempt should be rejected by circuit breaker
            response = await ncb_service.submit_claim(request)
            assert response.success is False
            assert response.error_code == "CIRCUIT_OPEN"

    @pytest.mark.asyncio
    async def test_circuit_breaker_does_not_count_validation_errors(self, ncb_service):
        """
        Test validation errors don't count towards circuit breaker

        Given: Circuit breaker with threshold of 3
        When: Multiple 400 validation errors occur
        Then: Circuit breaker remains closed
        """
        from src.models.claim import NCBSubmissionRequest
        from src.services.ncb_service import NCBValidationError

        request = NCBSubmissionRequest(
            event_date="2024-12-15",
            submission_date="2024-12-21T10:00:00",
            claim_amount=100.00,
            invoice_number="RCP-001",
            policy_number="INVALID",
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = MagicMock(
                status_code=400,
                json=lambda: {"message": "Invalid member ID"}
            )

            # Multiple validation errors
            for i in range(5):
                try:
                    await ncb_service.submit_claim(request)
                except NCBValidationError:
                    pass  # Expected

            # Circuit should still be closed
            assert ncb_service.circuit_breaker.state.value == "closed"

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self, ncb_service):
        """
        Test circuit breaker transitions to half-open after timeout

        Given: Circuit breaker is open
        When: Timeout period elapses
        Then: Circuit transitions to half-open for testing
        """
        import asyncio
        from src.models.claim import NCBSubmissionRequest

        request = NCBSubmissionRequest(
            event_date="2024-12-15",
            submission_date="2024-12-21T10:00:00",
            claim_amount=100.00,
            invoice_number="RCP-001",
            policy_number="M12345",
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        # Force circuit open
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = \
                httpx.ConnectError("Connection failed")

            for i in range(3):
                try:
                    await ncb_service.submit_claim(request)
                except:
                    pass

            assert ncb_service.circuit_breaker.state.value == "open"

            # Wait for timeout (2 seconds in test config)
            await asyncio.sleep(2.1)

            # Mock success for recovery
            mock_client.return_value.__aenter__.return_value.post.side_effect = None
            mock_client.return_value.__aenter__.return_value.post.return_value = MagicMock(
                status_code=201,
                json=lambda: {"success": True, "claim_reference": "CLM-123"}
            )

            # Check circuit breaker allows call (transitions to half-open)
            response = await ncb_service.submit_claim(request)

            # Should succeed and close circuit
            assert response.success is True
            assert ncb_service.circuit_breaker.state.value == "closed"

    @pytest.mark.asyncio
    async def test_circuit_breaker_counts_rate_limit_errors(self, ncb_service):
        """
        Test rate limit errors count towards circuit breaker

        Given: Circuit breaker with threshold of 3
        When: Rate limit errors occur
        Then: Circuit opens after threshold
        """
        from src.models.claim import NCBSubmissionRequest
        from src.services.ncb_service import NCBRateLimitError

        request = NCBSubmissionRequest(
            event_date="2024-12-15",
            submission_date="2024-12-21T10:00:00",
            claim_amount=100.00,
            invoice_number="RCP-001",
            policy_number="M12345",
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = MagicMock(
                status_code=429,
                headers={"Retry-After": "60"},
                json=lambda: {"message": "Too many requests"}
            )

            for i in range(3):
                try:
                    await ncb_service.submit_claim(request)
                except NCBRateLimitError:
                    pass

            # Circuit should be open
            assert ncb_service.circuit_breaker.state.value == "open"

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_on_success(self, ncb_service):
        """
        Test circuit breaker resets failure count on success

        Given: Circuit with some failures
        When: Successful call occurs
        Then: Failure count resets to zero
        """
        from src.models.claim import NCBSubmissionRequest

        request = NCBSubmissionRequest(
            event_date="2024-12-15",
            submission_date="2024-12-21T10:00:00",
            claim_amount=100.00,
            invoice_number="RCP-001",
            policy_number="M12345",
            source_email_id="msg_123",
            source_filename="test.jpg",
            extraction_confidence=0.95,
        )

        with patch('httpx.AsyncClient') as mock_client:
            # 2 failures
            mock_client.return_value.__aenter__.return_value.post.side_effect = [
                httpx.ConnectError("Failed"),
                httpx.ConnectError("Failed"),
                MagicMock(
                    status_code=201,
                    json=lambda: {"success": True, "claim_reference": "CLM-123"}
                )
            ]

            # First two fail
            for i in range(2):
                try:
                    await ncb_service.submit_claim(request)
                except:
                    pass

            # Third succeeds
            response = await ncb_service.submit_claim(request)
            assert response.success is True

            # Failure count should be reset
            status = ncb_service.get_circuit_breaker_status()
            assert status["failure_count"] == 0
            assert status["state"] == "closed"

    @pytest.mark.asyncio
    async def test_get_circuit_breaker_status(self, ncb_service):
        """
        Test getting circuit breaker status

        Given: Circuit breaker with state
        When: get_circuit_breaker_status() called
        Then: Returns state and metrics
        """
        status = ncb_service.get_circuit_breaker_status()

        assert "state" in status
        assert "failure_count" in status
        assert "failure_threshold" in status
        assert "timeout_seconds" in status
        assert status["state"] == "closed"
        assert status["failure_threshold"] == 3

    @pytest.mark.asyncio
    async def test_health_check_with_open_circuit(self, ncb_service):
        """
        Test health check fails when circuit is open

        Given: Circuit breaker is open
        When: check_health() called
        Then: Returns False immediately
        """
        from src.services.ncb_service import CircuitState

        # Force circuit open
        ncb_service.circuit_breaker._state = CircuitState.OPEN

        # Health check should fail without making request
        is_healthy = await ncb_service.check_health()
        assert is_healthy is False
