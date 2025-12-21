"""NCB API client for claim submission."""

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


class NCBConnectionError(Exception):
    """NCB API connection error."""

    pass


class NCBValidationError(Exception):
    """NCB API validation error."""

    pass


class NCBRateLimitError(Exception):
    """NCB API rate limit error."""

    pass


class NCBService:
    """NCB API integration for claim submission."""

    def __init__(self) -> None:
        """Initialize NCB API client."""
        self.config = settings.ncb
        self.base_url = self.config.api_base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.config.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        logger.info("NCB service initialized", base_url=self.base_url)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, max=60),
        retry=retry_if_exception_type(NCBConnectionError),
    )
    async def submit_claim(self, claim: NCBSubmissionRequest) -> NCBSubmissionResponse:
        """
        Submit extracted claim data to NCB.

        Args:
            claim: Structured claim data

        Returns:
            Submission response with claim reference

        Raises:
            NCBConnectionError: If API unreachable
            NCBValidationError: If data validation fails
            NCBRateLimitError: If rate limited
        """
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                logger.info(
                    "Submitting claim to NCB",
                    policy_number=claim.policy_number,
                    amount=claim.claim_amount,
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
                    return NCBSubmissionResponse(
                        success=True,
                        claim_reference=data.get("claim_reference"),
                    )

                elif response.status_code == 400:
                    data = response.json()
                    error_msg = data.get("message", "Validation failed")
                    logger.warning("Claim validation failed", error=error_msg)
                    raise NCBValidationError(error_msg)

                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    logger.warning("Rate limited by NCB API", retry_after=retry_after)
                    raise NCBRateLimitError(f"Rate limited, retry after {retry_after}s")

                elif response.status_code >= 500:
                    logger.error("NCB API server error", status=response.status_code)
                    raise NCBConnectionError(f"Server error: {response.status_code}")

                else:
                    logger.error("Unexpected NCB API response", status=response.status_code)
                    return NCBSubmissionResponse(
                        success=False,
                        error_code=f"HTTP_{response.status_code}",
                        error_message=response.text,
                    )

        except httpx.TimeoutException as e:
            logger.error("NCB API timeout", error=str(e))
            raise NCBConnectionError("API timeout") from e

        except httpx.ConnectError as e:
            logger.error("NCB API connection failed", error=str(e))
            raise NCBConnectionError("Connection failed") from e

        except (NCBValidationError, NCBRateLimitError):
            raise

        except Exception as e:
            logger.error("Unexpected error submitting to NCB", error=str(e))
            raise NCBConnectionError(str(e)) from e

    async def check_health(self) -> bool:
        """Check if NCB API is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers=self.headers,
                )
                return response.status_code == 200

        except Exception as e:
            logger.warning("NCB health check failed", error=str(e))
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
