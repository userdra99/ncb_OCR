"""
Field validators for claim data.

Validates extracted claim fields against business rules and Malaysian format requirements.
"""

import re
from typing import Dict, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValidationResult(BaseModel):
    """Result of field validation."""
    is_valid: bool
    format_valid: bool = True
    range_valid: bool = True
    suspicious: bool = False
    warnings: list[str] = []
    errors: list[str] = []


class FieldValidator:
    """Validates claim fields against business rules."""

    # Malaysian member ID pattern: 1-3 uppercase letters + 4-10 digits
    MEMBER_ID_PATTERN = re.compile(r'^[A-Z]{1,3}\d{4,10}$')

    # Receipt number pattern: 3-20 alphanumeric with hyphens/slashes
    RECEIPT_PATTERN = re.compile(r'^[A-Z0-9\-/]{3,20}$')

    # Malaysian naming particles
    MALAYSIAN_PARTICLES = ['bin', 'binti', 'a/l', 'a/p', 'al']

    # Provider keywords (clinic, hospital, doctor)
    PROVIDER_KEYWORDS = [
        'clinic', 'klinik', 'hospital', 'hospital',
        'dr', 'doctor', 'doktor', 'medical', 'perubatan',
        'health', 'kesihatan', 'pharmacy', 'farmasi',
        'dental', 'pergigian', 'optometrist', 'optik'
    ]

    @staticmethod
    def validate_member_id(member_id: Optional[str]) -> ValidationResult:
        """
        Validate member ID format.

        Rules:
        - 1-3 uppercase letters + 4-10 digits
        - Example: M12345, ABC123456

        Args:
            member_id: Member ID to validate

        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=False)

        if not member_id:
            result.errors.append("Member ID is required")
            result.format_valid = False
            return result

        # Strip whitespace
        member_id = member_id.strip().upper()

        # Check format
        if not FieldValidator.MEMBER_ID_PATTERN.match(member_id):
            result.errors.append(
                "Member ID must be 1-3 uppercase letters followed by 4-10 digits"
            )
            result.format_valid = False
            return result

        result.is_valid = True
        logger.debug(f"Member ID validation passed: {member_id}")
        return result

    @staticmethod
    def validate_member_name(name: Optional[str]) -> ValidationResult:
        """
        Validate member name.

        Rules:
        - 2-100 characters
        - At least first and last name (or single name with particle)
        - Supports Malaysian naming (bin, binti, a/l, a/p)

        Args:
            name: Member name to validate

        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=False)

        if not name:
            result.errors.append("Member name is required")
            result.format_valid = False
            return result

        # Strip whitespace
        name = name.strip()

        # Check length
        if len(name) < 2:
            result.errors.append("Member name must be at least 2 characters")
            result.format_valid = False
            return result

        if len(name) > 100:
            result.errors.append("Member name must not exceed 100 characters")
            result.format_valid = False
            return result

        # Check for at least two parts (first and last name)
        # or one part with Malaysian particle
        name_parts = name.split()
        has_particle = any(
            part.lower() in FieldValidator.MALAYSIAN_PARTICLES
            for part in name_parts
        )

        if len(name_parts) < 2 and not has_particle:
            result.warnings.append(
                "Name should contain at least first and last name"
            )
            result.suspicious = True

        result.is_valid = True
        logger.debug(f"Member name validation passed: {name}")
        return result

    @staticmethod
    def validate_amount(amount: Optional[float]) -> ValidationResult:
        """
        Validate claim amount.

        Rules:
        - Positive number
        - Between RM 1.00 and RM 1,000,000
        - Flag amounts > RM 10,000 as suspicious

        Args:
            amount: Claim amount to validate

        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=False)

        if amount is None:
            result.errors.append("Amount is required")
            result.range_valid = False
            return result

        # Check positive
        if amount <= 0:
            result.errors.append("Amount must be positive")
            result.range_valid = False
            return result

        # Check minimum
        if amount < 1.0:
            result.errors.append("Amount must be at least RM 1.00")
            result.range_valid = False
            return result

        # Check maximum
        if amount > 1_000_000.0:
            result.errors.append("Amount exceeds maximum of RM 1,000,000")
            result.range_valid = False
            return result

        # Flag suspicious amounts
        if amount > 10_000.0:
            result.warnings.append(
                f"Amount RM {amount:,.2f} is unusually high (>RM 10,000)"
            )
            result.suspicious = True

        result.is_valid = True
        logger.debug(f"Amount validation passed: RM {amount:,.2f}")
        return result

    @staticmethod
    def validate_service_date(service_date: Optional[datetime]) -> ValidationResult:
        """
        Validate service date.

        Rules:
        - Not in the future
        - Not before 1900
        - Not older than 2 years (warn)

        Args:
            service_date: Service date to validate

        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=False)

        if not service_date:
            result.errors.append("Service date is required")
            result.range_valid = False
            return result

        now = datetime.now()
        min_date = datetime(1900, 1, 1)
        two_years_ago = now - timedelta(days=730)

        # Check not in future
        if service_date > now:
            result.errors.append("Service date cannot be in the future")
            result.range_valid = False
            return result

        # Check not before 1900
        if service_date < min_date:
            result.errors.append("Service date cannot be before 1900")
            result.range_valid = False
            return result

        # Warn if older than 2 years
        if service_date < two_years_ago:
            result.warnings.append(
                f"Service date is more than 2 years old ({service_date.strftime('%Y-%m-%d')})"
            )
            result.suspicious = True

        result.is_valid = True
        logger.debug(f"Service date validation passed: {service_date.strftime('%Y-%m-%d')}")
        return result

    @staticmethod
    def validate_receipt_number(receipt_number: Optional[str]) -> ValidationResult:
        """
        Validate receipt/invoice number.

        Rules:
        - 3-20 alphanumeric characters
        - May contain hyphens and slashes

        Args:
            receipt_number: Receipt number to validate

        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=False)

        if not receipt_number:
            result.errors.append("Receipt number is required")
            result.format_valid = False
            return result

        # Strip whitespace and uppercase
        receipt_number = receipt_number.strip().upper()

        # Check format
        if not FieldValidator.RECEIPT_PATTERN.match(receipt_number):
            result.errors.append(
                "Receipt number must be 3-20 alphanumeric characters (hyphens and slashes allowed)"
            )
            result.format_valid = False
            return result

        result.is_valid = True
        logger.debug(f"Receipt number validation passed: {receipt_number}")
        return result

    @staticmethod
    def validate_provider_name(provider_name: Optional[str]) -> ValidationResult:
        """
        Validate provider name.

        Rules:
        - 3-200 characters
        - Should contain clinic/hospital/doctor keywords

        Args:
            provider_name: Provider name to validate

        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=False)

        if not provider_name:
            result.errors.append("Provider name is required")
            result.format_valid = False
            return result

        # Strip whitespace
        provider_name = provider_name.strip()

        # Check length
        if len(provider_name) < 3:
            result.errors.append("Provider name must be at least 3 characters")
            result.format_valid = False
            return result

        if len(provider_name) > 200:
            result.errors.append("Provider name must not exceed 200 characters")
            result.format_valid = False
            return result

        # Check for provider keywords
        provider_lower = provider_name.lower()
        has_keyword = any(
            keyword in provider_lower
            for keyword in FieldValidator.PROVIDER_KEYWORDS
        )

        if not has_keyword:
            result.warnings.append(
                "Provider name does not contain typical healthcare keywords"
            )
            result.suspicious = True

        result.is_valid = True
        logger.debug(f"Provider name validation passed: {provider_name}")
        return result

    @staticmethod
    def validate_all_fields(claim_data: dict) -> Dict[str, ValidationResult]:
        """
        Validate all fields in a claim.

        Args:
            claim_data: Dictionary with claim fields

        Returns:
            Dictionary mapping field names to ValidationResults
        """
        results = {}

        # Validate required fields
        results['member_id'] = FieldValidator.validate_member_id(
            claim_data.get('member_id')
        )

        results['member_name'] = FieldValidator.validate_member_name(
            claim_data.get('member_name')
        )

        results['total_amount'] = FieldValidator.validate_amount(
            claim_data.get('total_amount')
        )

        results['service_date'] = FieldValidator.validate_service_date(
            claim_data.get('service_date')
        )

        results['receipt_number'] = FieldValidator.validate_receipt_number(
            claim_data.get('receipt_number')
        )

        results['provider_name'] = FieldValidator.validate_provider_name(
            claim_data.get('provider_name')
        )

        # Log overall validation result
        all_valid = all(r.is_valid for r in results.values())
        has_warnings = any(r.warnings for r in results.values())

        if all_valid:
            if has_warnings:
                logger.info(
                    "Claim validation passed with warnings",
                    extra={
                        'member_id': claim_data.get('member_id'),
                        'warnings': sum(len(r.warnings) for r in results.values())
                    }
                )
            else:
                logger.info(
                    "Claim validation passed",
                    extra={'member_id': claim_data.get('member_id')}
                )
        else:
            error_count = sum(len(r.errors) for r in results.values())
            logger.warning(
                "Claim validation failed",
                extra={
                    'member_id': claim_data.get('member_id'),
                    'errors': error_count
                }
            )

        return results
