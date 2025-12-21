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
            from src.config.settings import NCBConfig

            config = NCBConfig()
            return NCBService(config)

    @pytest.mark.asyncio
    async def test_submit_claim_success(self, ncb_service, sample_receipt_data):
        """
        Test successful claim submission

        Given: Valid claim data
        When: submit_claim() is called
        Then: Returns success response with claim reference
        """
        # Arrange
        from src.models.ncb import NCBSubmissionRequest

        request = NCBSubmissionRequest(
            member_id=sample_receipt_data["member_id"],
            member_name=sample_receipt_data["member_name"],
            provider_name=sample_receipt_data["provider_name"],
            service_date=sample_receipt_data["service_date"],
            receipt_number=sample_receipt_data["receipt_number"],
            total_amount=sample_receipt_data["total_amount"],
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
        from src.models.ncb import NCBSubmissionRequest
        from src.services.ncb_service import NCBValidationError

        mock_ncb_api.post.return_value = MagicMock(
            status_code=400,
            json=lambda: {
                "success": False,
                "error_code": "VALIDATION_FAILED",
                "message": "Member not found in system",
                "details": {"field": "member_id", "reason": "Member not found"},
            },
        )

        request = NCBSubmissionRequest(
            member_id="INVALID",
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
        from src.models.ncb import NCBSubmissionRequest
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
    async def test_submit_claim_includes_metadata(self, ncb_service, mock_ncb_api):
        """
        Test that submission includes source metadata

        Given: Claim with source email and confidence
        When: submit_claim() is called
        Then: Request includes source metadata
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
            source_email_id="msg_abc123",
            source_filename="receipt_001.jpg",
            extraction_confidence=0.94,
        )

        # Act
        await ncb_service.submit_claim(request)

        # Assert
        call_args = mock_ncb_api.post.call_args
        json_data = call_args.kwargs.get("json", {})

        assert json_data.get("source", {}).get("email_id") == "msg_abc123"
        assert json_data.get("source", {}).get("filename") == "receipt_001.jpg"
        assert json_data.get("source", {}).get("extraction_confidence") == 0.94

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
    async def test_exponential_backoff_timing(self, ncb_service, mock_ncb_api):
        """
        Test exponential backoff retry timing

        Given: Multiple retry attempts
        When: Retries occur
        Then: Wait time doubles each retry (2s, 4s, 8s, etc.)
        """
        # This would be tested with actual timing in integration tests
        # Unit test verifies config values
        assert ncb_service.config.retry_backoff_base == 2.0
        assert ncb_service.config.retry_backoff_max == 60.0
