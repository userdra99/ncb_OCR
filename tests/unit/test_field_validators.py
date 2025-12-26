"""
Unit tests for field validators.

Tests all validator functions with Malaysian-specific validation,
boundary cases, and format validation.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal

from src.services.field_validators import (
    validate_member_id,
    validate_total_amount,
    validate_service_date,
    validate_provider_name,
    validate_receipt_number,
    validate_phone_number,
    validate_ic_number,
    validate_gst_sst_amount,
    validate_email_address,
    ValidationError
)


class TestMemberIDValidator:
    """Test member_id validation."""

    def test_valid_member_id(self):
        """Valid member IDs should pass."""
        assert validate_member_id("M12345") is True
        assert validate_member_id("M00001") is True
        assert validate_member_id("M99999") is True

    def test_invalid_prefix(self):
        """Invalid prefix should fail."""
        with pytest.raises(ValidationError, match="must start with 'M'"):
            validate_member_id("A12345")

        with pytest.raises(ValidationError, match="must start with 'M'"):
            validate_member_id("12345")

    def test_invalid_length(self):
        """Invalid length should fail."""
        with pytest.raises(ValidationError, match="must be exactly 6 characters"):
            validate_member_id("M123")

        with pytest.raises(ValidationError, match="must be exactly 6 characters"):
            validate_member_id("M1234567")

    def test_invalid_characters(self):
        """Non-alphanumeric characters should fail."""
        with pytest.raises(ValidationError, match="must contain only alphanumeric"):
            validate_member_id("M123-5")

        with pytest.raises(ValidationError, match="must contain only alphanumeric"):
            validate_member_id("M123 5")

    def test_lowercase_prefix(self):
        """Lowercase prefix should fail (case-sensitive)."""
        with pytest.raises(ValidationError, match="must start with 'M'"):
            validate_member_id("m12345")

    def test_none_value(self):
        """None should fail."""
        with pytest.raises(ValidationError, match="Member ID is required"):
            validate_member_id(None)

    def test_empty_string(self):
        """Empty string should fail."""
        with pytest.raises(ValidationError, match="Member ID is required"):
            validate_member_id("")

    def test_whitespace_only(self):
        """Whitespace-only should fail."""
        with pytest.raises(ValidationError, match="Member ID is required"):
            validate_member_id("   ")


class TestTotalAmountValidator:
    """Test total_amount validation."""

    def test_valid_amounts(self):
        """Valid amounts should pass."""
        assert validate_total_amount(Decimal("100.00")) is True
        assert validate_total_amount(Decimal("0.01")) is True
        assert validate_total_amount(Decimal("9999.99")) is True
        assert validate_total_amount(Decimal("1234.56")) is True

    def test_zero_amount(self):
        """Zero amount should fail."""
        with pytest.raises(ValidationError, match="must be greater than 0"):
            validate_total_amount(Decimal("0.00"))

    def test_negative_amount(self):
        """Negative amount should fail."""
        with pytest.raises(ValidationError, match="must be greater than 0"):
            validate_total_amount(Decimal("-50.00"))

    def test_max_amount_exceeded(self):
        """Amount exceeding max should fail."""
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_total_amount(Decimal("100000.00"))

        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_total_amount(Decimal("999999.99"))

    def test_invalid_decimal_places(self):
        """More than 2 decimal places should fail."""
        with pytest.raises(ValidationError, match="must have at most 2 decimal places"):
            validate_total_amount(Decimal("100.123"))

        with pytest.raises(ValidationError, match="must have at most 2 decimal places"):
            validate_total_amount(Decimal("50.999"))

    def test_none_value(self):
        """None should fail."""
        with pytest.raises(ValidationError, match="Total amount is required"):
            validate_total_amount(None)

    def test_string_conversion(self):
        """String amounts should be converted and validated."""
        assert validate_total_amount("100.00") is True
        assert validate_total_amount("50.5") is True

    def test_invalid_string(self):
        """Invalid string should fail."""
        with pytest.raises(ValidationError, match="must be a valid number"):
            validate_total_amount("invalid")

        with pytest.raises(ValidationError, match="must be a valid number"):
            validate_total_amount("RM 100")


class TestServiceDateValidator:
    """Test service_date validation."""

    def test_valid_dates(self):
        """Valid dates should pass."""
        assert validate_service_date(date.today()) is True
        assert validate_service_date(date.today() - timedelta(days=1)) is True
        assert validate_service_date(date.today() - timedelta(days=30)) is True

    def test_future_date(self):
        """Future dates should fail."""
        future_date = date.today() + timedelta(days=1)
        with pytest.raises(ValidationError, match="cannot be in the future"):
            validate_service_date(future_date)

    def test_date_too_old(self):
        """Dates older than 2 years should fail."""
        old_date = date.today() - timedelta(days=731)  # > 2 years
        with pytest.raises(ValidationError, match="cannot be older than 2 years"):
            validate_service_date(old_date)

    def test_date_exactly_2_years(self):
        """Date exactly 2 years ago should pass."""
        two_years_ago = date.today() - timedelta(days=730)
        assert validate_service_date(two_years_ago) is True

    def test_none_value(self):
        """None should fail."""
        with pytest.raises(ValidationError, match="Service date is required"):
            validate_service_date(None)

    def test_string_date_conversion(self):
        """String dates should be converted and validated."""
        assert validate_service_date("2024-01-15") is True
        assert validate_service_date("15/01/2024") is True  # DD/MM/YYYY
        assert validate_service_date("15-01-2024") is True  # DD-MM-YYYY

    def test_invalid_string_date(self):
        """Invalid string dates should fail."""
        with pytest.raises(ValidationError, match="must be a valid date"):
            validate_service_date("invalid")

        with pytest.raises(ValidationError, match="must be a valid date"):
            validate_service_date("32/01/2024")


class TestProviderNameValidator:
    """Test provider_name validation."""

    def test_valid_names(self):
        """Valid provider names should pass."""
        assert validate_provider_name("Klinik Dr. Ahmad") is True
        assert validate_provider_name("Hospital Pantai") is True
        assert validate_provider_name("Dr. Lee Medical Centre") is True
        assert validate_provider_name("Farmasi Kesihatan") is True

    def test_min_length(self):
        """Names too short should fail."""
        with pytest.raises(ValidationError, match="must be at least 2 characters"):
            validate_provider_name("A")

        with pytest.raises(ValidationError, match="must be at least 2 characters"):
            validate_provider_name("Dr")

    def test_max_length(self):
        """Names too long should fail."""
        long_name = "A" * 201
        with pytest.raises(ValidationError, match="must be at most 200 characters"):
            validate_provider_name(long_name)

    def test_invalid_characters(self):
        """Names with invalid characters should fail."""
        with pytest.raises(ValidationError, match="contains invalid characters"):
            validate_provider_name("Klinik@Ahmad")

        with pytest.raises(ValidationError, match="contains invalid characters"):
            validate_provider_name("Hospital<script>")

    def test_valid_characters(self):
        """Names with valid special characters should pass."""
        assert validate_provider_name("Dr. O'Brien") is True
        assert validate_provider_name("Klinik & Farmasi") is True
        assert validate_provider_name("Hospital (Kuala Lumpur)") is True

    def test_none_value(self):
        """None should fail."""
        with pytest.raises(ValidationError, match="Provider name is required"):
            validate_provider_name(None)

    def test_empty_string(self):
        """Empty string should fail."""
        with pytest.raises(ValidationError, match="Provider name is required"):
            validate_provider_name("")

    def test_whitespace_trimming(self):
        """Leading/trailing whitespace should be trimmed."""
        assert validate_provider_name("  Klinik Ahmad  ") is True


class TestReceiptNumberValidator:
    """Test receipt_number validation."""

    def test_valid_receipt_numbers(self):
        """Valid receipt numbers should pass."""
        assert validate_receipt_number("RCP-001") is True
        assert validate_receipt_number("INV12345") is True
        assert validate_receipt_number("REC/2024/001") is True
        assert validate_receipt_number("12345") is True

    def test_min_length(self):
        """Receipt numbers too short should fail."""
        with pytest.raises(ValidationError, match="must be at least 3 characters"):
            validate_receipt_number("12")

        with pytest.raises(ValidationError, match="must be at least 3 characters"):
            validate_receipt_number("AB")

    def test_max_length(self):
        """Receipt numbers too long should fail."""
        long_number = "A" * 51
        with pytest.raises(ValidationError, match="must be at most 50 characters"):
            validate_receipt_number(long_number)

    def test_invalid_characters(self):
        """Receipt numbers with invalid characters should fail."""
        with pytest.raises(ValidationError, match="contains invalid characters"):
            validate_receipt_number("RCP<001>")

        with pytest.raises(ValidationError, match="contains invalid characters"):
            validate_receipt_number("RCP@001")

    def test_valid_characters(self):
        """Receipt numbers with valid characters should pass."""
        assert validate_receipt_number("RCP-001") is True
        assert validate_receipt_number("INV/2024/001") is True
        assert validate_receipt_number("REC_12345") is True

    def test_none_value(self):
        """None should fail."""
        with pytest.raises(ValidationError, match="Receipt number is required"):
            validate_receipt_number(None)


class TestPhoneNumberValidator:
    """Test Malaysian phone number validation."""

    def test_valid_mobile_numbers(self):
        """Valid Malaysian mobile numbers should pass."""
        assert validate_phone_number("0123456789") is True
        assert validate_phone_number("0167890123") is True
        assert validate_phone_number("0198765432") is True

    def test_valid_landline_numbers(self):
        """Valid Malaysian landline numbers should pass."""
        assert validate_phone_number("0312345678") is True
        assert validate_phone_number("0387654321") is True

    def test_with_country_code(self):
        """Numbers with +60 country code should pass."""
        assert validate_phone_number("+60123456789") is True
        assert validate_phone_number("+60312345678") is True

    def test_with_dash_formatting(self):
        """Numbers with dashes should pass."""
        assert validate_phone_number("012-345-6789") is True
        assert validate_phone_number("03-1234-5678") is True

    def test_with_spaces(self):
        """Numbers with spaces should pass."""
        assert validate_phone_number("012 345 6789") is True
        assert validate_phone_number("03 1234 5678") is True

    def test_invalid_prefix(self):
        """Numbers with invalid prefix should fail."""
        with pytest.raises(ValidationError, match="must start with 01"):
            validate_phone_number("0912345678")

    def test_invalid_length(self):
        """Numbers with invalid length should fail."""
        with pytest.raises(ValidationError, match="must be 10 or 11 digits"):
            validate_phone_number("012345")

        with pytest.raises(ValidationError, match="must be 10 or 11 digits"):
            validate_phone_number("012345678901")

    def test_none_value(self):
        """None should be allowed (optional field)."""
        assert validate_phone_number(None) is True


class TestICNumberValidator:
    """Test Malaysian IC number validation."""

    def test_valid_ic_numbers(self):
        """Valid Malaysian IC numbers should pass."""
        assert validate_ic_number("900101-01-1234") is True
        assert validate_ic_number("850615-14-5678") is True
        assert validate_ic_number("001231-10-9876") is True

    def test_without_dashes(self):
        """IC numbers without dashes should pass."""
        assert validate_ic_number("900101011234") is True
        assert validate_ic_number("850615145678") is True

    def test_invalid_format(self):
        """IC numbers with invalid format should fail."""
        with pytest.raises(ValidationError, match="must be in format YYMMDD-PP-NNNN"):
            validate_ic_number("90-01-01-01-1234")

        with pytest.raises(ValidationError, match="must be in format YYMMDD-PP-NNNN"):
            validate_ic_number("9001011234")  # Too short

    def test_invalid_date(self):
        """IC numbers with invalid date should fail."""
        with pytest.raises(ValidationError, match="contains invalid date"):
            validate_ic_number("900231-01-1234")  # Feb 31

        with pytest.raises(ValidationError, match="contains invalid date"):
            validate_ic_number("901301-01-1234")  # Month 13

    def test_invalid_state_code(self):
        """IC numbers with invalid state code should fail."""
        with pytest.raises(ValidationError, match="contains invalid state code"):
            validate_ic_number("900101-99-1234")  # Invalid state

    def test_none_value(self):
        """None should be allowed (optional field)."""
        assert validate_ic_number(None) is True


class TestGSTSSTAmountValidator:
    """Test GST/SST amount validation."""

    def test_valid_gst_amount(self):
        """Valid GST amount (6%) should pass."""
        total_amount = Decimal("100.00")
        gst_amount = Decimal("6.00")
        assert validate_gst_sst_amount(gst_amount, total_amount, "GST") is True

    def test_valid_sst_amount(self):
        """Valid SST amount (10%) should pass."""
        total_amount = Decimal("100.00")
        sst_amount = Decimal("10.00")
        assert validate_gst_sst_amount(sst_amount, total_amount, "SST") is True

    def test_zero_tax(self):
        """Zero tax amount should pass."""
        total_amount = Decimal("100.00")
        assert validate_gst_sst_amount(Decimal("0.00"), total_amount, "GST") is True

    def test_negative_tax(self):
        """Negative tax amount should fail."""
        total_amount = Decimal("100.00")
        with pytest.raises(ValidationError, match="cannot be negative"):
            validate_gst_sst_amount(Decimal("-5.00"), total_amount, "GST")

    def test_exceeds_total(self):
        """Tax exceeding total amount should fail."""
        total_amount = Decimal("100.00")
        with pytest.raises(ValidationError, match="cannot exceed total amount"):
            validate_gst_sst_amount(Decimal("150.00"), total_amount, "GST")

    def test_exceeds_expected_rate(self):
        """Tax exceeding expected rate by >20% should warn."""
        total_amount = Decimal("100.00")
        high_gst = Decimal("8.00")  # Expected 6%, got 8%
        # Should still pass but may log warning
        assert validate_gst_sst_amount(high_gst, total_amount, "GST") is True

    def test_none_value(self):
        """None should be allowed (optional field)."""
        total_amount = Decimal("100.00")
        assert validate_gst_sst_amount(None, total_amount, "GST") is True

    def test_invalid_tax_type(self):
        """Invalid tax type should fail."""
        total_amount = Decimal("100.00")
        with pytest.raises(ValidationError, match="must be 'GST' or 'SST'"):
            validate_gst_sst_amount(Decimal("6.00"), total_amount, "VAT")


class TestEmailAddressValidator:
    """Test email address validation."""

    def test_valid_emails(self):
        """Valid email addresses should pass."""
        assert validate_email_address("user@example.com") is True
        assert validate_email_address("test.user@domain.co.my") is True
        assert validate_email_address("admin+tag@company.com") is True

    def test_invalid_format(self):
        """Invalid email formats should fail."""
        with pytest.raises(ValidationError, match="must be a valid email"):
            validate_email_address("invalid")

        with pytest.raises(ValidationError, match="must be a valid email"):
            validate_email_address("@example.com")

        with pytest.raises(ValidationError, match="must be a valid email"):
            validate_email_address("user@")

    def test_none_value(self):
        """None should be allowed (optional field)."""
        assert validate_email_address(None) is True

    def test_empty_string(self):
        """Empty string should be allowed (optional field)."""
        assert validate_email_address("") is True


class TestValidationErrorHandling:
    """Test validation error handling."""

    def test_validation_error_message(self):
        """ValidationError should have descriptive message."""
        try:
            validate_member_id("INVALID")
        except ValidationError as e:
            assert "member_id" in str(e).lower()
            assert "must start with 'M'" in str(e)

    def test_validation_error_field_name(self):
        """ValidationError should include field name."""
        try:
            validate_total_amount(Decimal("-50.00"))
        except ValidationError as e:
            assert hasattr(e, "field_name") or "total_amount" in str(e).lower()

    def test_multiple_validation_errors(self):
        """Multiple validation errors should be caught."""
        errors = []

        try:
            validate_member_id("INVALID")
        except ValidationError as e:
            errors.append(e)

        try:
            validate_total_amount(Decimal("-50.00"))
        except ValidationError as e:
            errors.append(e)

        assert len(errors) == 2
