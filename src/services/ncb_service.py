"""NCB API client for claim submission."""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import settings
from src.models.claim import NCBSubmissionRequest, NCBSubmissionResponse
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class NCBConnectionError(Exception):
    """NCB API connection error."""

    pass


class NCBValidationError(Exception):
    """NCB API validation error."""

    pass


class NCBRateLimitError(Exception):
    """NCB API rate limit error."""

    pass


class NCBCircuitBreakerError(Exception):
    """Circuit breaker is open, rejecting requests."""

    pass


class CircuitBreaker:
    """
    Thread-safe circuit breaker implementation.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failure threshold exceeded, requests rejected
    - HALF_OPEN: Testing if service recovered, limited requests allowed

    Configuration:
    - failure_threshold: Number of failures before opening circuit (default: 5)
    - timeout_seconds: Time to wait before attempting recovery (default: 60)
    - half_open_max_calls: Max calls allowed in half-open state (default: 3)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 3,
    ) -> None:
        """Initialize circuit breaker."""
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = Lock()

        logger.info(
            "Circuit breaker initialized",
            failure_threshold=failure_threshold,
            timeout_seconds=timeout_seconds,
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return False

        elapsed = datetime.now() - self._last_failure_time
        return elapsed > timedelta(seconds=self.timeout_seconds)

    def _transition_state(self, new_state: CircuitState, reason: str) -> None:
        """Transition to new state with logging."""
        old_state = self._state
        self._state = new_state

        logger.warning(
            "Circuit breaker state transition",
            old_state=old_state.value,
            new_state=new_state.value,
            reason=reason,
            failure_count=self._failure_count,
        )

    def call_allowed(self) -> bool:
        """
        Check if a call is allowed through the circuit breaker.

        Returns:
            True if call should proceed, False if rejected

        Raises:
            NCBCircuitBreakerError: If circuit is open
        """
        with self._lock:
            # Check if we should attempt recovery
            if self._state == CircuitState.OPEN and self._should_attempt_reset():
                self._transition_state(
                    CircuitState.HALF_OPEN, "Timeout elapsed, testing recovery"
                )
                self._half_open_calls = 0

            # Handle different states
            if self._state == CircuitState.CLOSED:
                return True

            elif self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    logger.info(
                        "Circuit breaker allowing test call",
                        test_call=self._half_open_calls,
                        max_calls=self.half_open_max_calls,
                    )
                    return True
                else:
                    raise NCBCircuitBreakerError(
                        "Circuit breaker in half-open state, max test calls reached"
                    )

            elif self._state == CircuitState.OPEN:
                time_until_retry = self.timeout_seconds
                if self._last_failure_time:
                    elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                    time_until_retry = max(0, self.timeout_seconds - elapsed)

                raise NCBCircuitBreakerError(
                    f"Circuit breaker open, retry in {time_until_retry:.0f}s"
                )

            return False

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._transition_state(CircuitState.CLOSED, "Recovery successful")
                self._failure_count = 0
                self._last_failure_time = None

            # In closed state, reset failure count on success
            elif self._state == CircuitState.CLOSED:
                if self._failure_count > 0:
                    logger.info(
                        "Resetting failure count after success",
                        previous_failures=self._failure_count,
                    )
                    self._failure_count = 0

    def record_failure(self, error: Exception, is_retryable: bool = True) -> None:
        """
        Record a failed call.

        Args:
            error: The exception that occurred
            is_retryable: Whether this failure should count towards circuit opening
        """
        with self._lock:
            # Don't count non-retryable errors (like validation errors)
            if not is_retryable:
                logger.debug(
                    "Non-retryable error, not counting towards circuit breaker",
                    error_type=type(error).__name__,
                )
                return

            self._failure_count += 1
            self._last_failure_time = datetime.now()

            logger.warning(
                "Circuit breaker recorded failure",
                failure_count=self._failure_count,
                threshold=self.failure_threshold,
                error_type=type(error).__name__,
            )

            # Check if we should open the circuit
            if self._state == CircuitState.HALF_OPEN:
                self._transition_state(
                    CircuitState.OPEN, "Failure during recovery test"
                )

            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                self._transition_state(
                    CircuitState.OPEN,
                    f"Failure threshold reached ({self._failure_count}/{self.failure_threshold})",
                )

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        with self._lock:
            old_state = self._state
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0

            logger.info("Circuit breaker manually reset", previous_state=old_state.value)


class NCBService:
    """NCB API integration for claim submission with circuit breaker."""

    def __init__(
        self,
        failure_threshold: int = 5,
        circuit_timeout: int = 60,
    ) -> None:
        """
        Initialize NCB API client with circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            circuit_timeout: Seconds to wait before attempting recovery
        """
        self.config = settings.ncb
        self.base_url = self.config.api_base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.config.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            timeout_seconds=circuit_timeout,
        )

        logger.info(
            "NCB service initialized with circuit breaker",
            base_url=self.base_url,
            failure_threshold=failure_threshold,
            circuit_timeout=circuit_timeout,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, max=60),
        retry=retry_if_exception_type(NCBConnectionError),
    )
    async def submit_claim(self, claim: NCBSubmissionRequest) -> NCBSubmissionResponse:
        """
        Submit extracted claim data to NCB with circuit breaker protection.

        Args:
            claim: Structured claim data

        Returns:
            Submission response with claim reference

        Raises:
            NCBCircuitBreakerError: If circuit breaker is open
            NCBConnectionError: If API unreachable
            NCBValidationError: If data validation fails (400)
            NCBRateLimitError: If rate limited (429)
        """
        # Check circuit breaker before attempting call
        try:
            self.circuit_breaker.call_allowed()
        except NCBCircuitBreakerError as e:
            logger.error(
                "Circuit breaker rejected claim submission",
                circuit_state=self.circuit_breaker.state.value,
                error=str(e),
            )
            return NCBSubmissionResponse(
                success=False,
                error_code="CIRCUIT_OPEN",
                error_message=str(e),
            )

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                logger.info(
                    "Submitting claim to NCB",
                    policy_number=claim.policy_number,
                    amount=claim.claim_amount,
                    circuit_state=self.circuit_breaker.state.value,
                )

                response = await client.post(
                    f"{self.base_url}/claims/submit",
                    json=claim.model_dump(by_alias=True),  # Use NCB field names
                    headers=self.headers,
                )

                # Handle different status codes
                if response.status_code == 201:
                    data = response.json()
                    logger.info(
                        "Claim submitted successfully",
                        claim_reference=data.get("claim_reference"),
                    )
                    # Record success with circuit breaker
                    self.circuit_breaker.record_success()
                    return NCBSubmissionResponse(
                        success=True,
                        claim_reference=data.get("claim_reference"),
                    )

                elif response.status_code == 400:
                    # Validation errors - don't count towards circuit breaker
                    data = response.json()
                    error_msg = data.get("message", "Validation failed")
                    logger.warning("Claim validation failed", error=error_msg)
                    error = NCBValidationError(error_msg)
                    self.circuit_breaker.record_failure(error, is_retryable=False)
                    raise error

                elif response.status_code == 401:
                    # Authentication error - don't count towards circuit breaker
                    logger.error("NCB API authentication failed")
                    error = NCBValidationError("Authentication failed")
                    self.circuit_breaker.record_failure(error, is_retryable=False)
                    raise error

                elif response.status_code == 403:
                    # Authorization error - don't count towards circuit breaker
                    logger.error("NCB API authorization failed")
                    error = NCBValidationError("Authorization failed")
                    self.circuit_breaker.record_failure(error, is_retryable=False)
                    raise error

                elif response.status_code == 429:
                    # Rate limit - count towards circuit breaker
                    retry_after = response.headers.get("Retry-After", "60")
                    logger.warning("Rate limited by NCB API", retry_after=retry_after)
                    error = NCBRateLimitError(f"Rate limited, retry after {retry_after}s")
                    self.circuit_breaker.record_failure(error, is_retryable=True)
                    raise error

                elif response.status_code >= 500:
                    # Server errors - count towards circuit breaker
                    logger.error("NCB API server error", status=response.status_code)
                    error = NCBConnectionError(f"Server error: {response.status_code}")
                    self.circuit_breaker.record_failure(error, is_retryable=True)
                    raise error

                else:
                    # Other errors - log but return response
                    logger.error("Unexpected NCB API response", status=response.status_code)
                    # Count as failure
                    error = NCBConnectionError(f"Unexpected status: {response.status_code}")
                    self.circuit_breaker.record_failure(error, is_retryable=True)
                    return NCBSubmissionResponse(
                        success=False,
                        error_code=f"HTTP_{response.status_code}",
                        error_message=response.text,
                    )

        except httpx.TimeoutException as e:
            logger.error("NCB API timeout", error=str(e))
            error = NCBConnectionError("API timeout")
            self.circuit_breaker.record_failure(error, is_retryable=True)
            raise error from e

        except httpx.ConnectError as e:
            logger.error("NCB API connection failed", error=str(e))
            error = NCBConnectionError("Connection failed")
            self.circuit_breaker.record_failure(error, is_retryable=True)
            raise error from e

        except (NCBValidationError, NCBRateLimitError):
            # Already recorded in circuit breaker
            raise

        except NCBConnectionError:
            # Already recorded in circuit breaker
            raise

        except Exception as e:
            logger.error("Unexpected error submitting to NCB", error=str(e))
            error = NCBConnectionError(str(e))
            self.circuit_breaker.record_failure(error, is_retryable=True)
            raise error from e

    def get_circuit_breaker_status(self) -> dict:
        """
        Get current circuit breaker status.

        Returns:
            Dictionary with circuit breaker state and metrics
        """
        with self.circuit_breaker._lock:
            return {
                "state": self.circuit_breaker.state.value,
                "failure_count": self.circuit_breaker._failure_count,
                "failure_threshold": self.circuit_breaker.failure_threshold,
                "last_failure_time": (
                    self.circuit_breaker._last_failure_time.isoformat()
                    if self.circuit_breaker._last_failure_time
                    else None
                ),
                "timeout_seconds": self.circuit_breaker.timeout_seconds,
            }

    async def check_health(self) -> bool:
        """
        Check if NCB API is available.

        Also checks circuit breaker state.
        """
        # If circuit is open, health check fails immediately
        if self.circuit_breaker.state == CircuitState.OPEN:
            logger.warning(
                "Health check failed - circuit breaker is open",
                circuit_status=self.get_circuit_breaker_status(),
            )
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers=self.headers,
                )

                if response.status_code == 200:
                    # Successful health check can help circuit recovery
                    self.circuit_breaker.record_success()
                    return True
                else:
                    return False

        except Exception as e:
            logger.warning("NCB health check failed", error=str(e))
            # Don't count health check failures towards circuit breaker
            # since they're informational
            return False

    async def get_claim_status(self, reference: str) -> Optional[dict]:
        """Get status of submitted claim."""
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.get(
                    f"{self.base_url}/claims/{reference}",
                    headers=self.headers,
                )

                if response.status_code == 200:
                    return response.json()

                return None

        except Exception as e:
            logger.error("Failed to get claim status", reference=reference, error=str(e))
            return None
