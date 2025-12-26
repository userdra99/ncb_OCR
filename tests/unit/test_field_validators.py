"""
Unit tests for field validators.

Tests all validator functions with Malaysian-specific validation,
boundary cases, and format validation.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from src.utils.field_validators import FieldValidator, ValidationResult


class TestMemberIDValidator:
    """Test member_id validation."""

    def test_valid_member_id(self):
        """Valid member IDs should pass."""
        result = FieldValidator.validate_member_id("M12345")
        assert result.is_valid is True
        assert result.format_valid is True
        assert len(result.errors) == 0

        result = FieldValidator.validate_member_id("M00001")
        assert result.is_valid is True

        result = FieldValidator.validate_member_id("ABC123456")
        assert result.is_valid is True

    def test_invalid_prefix(self):
        """Invalid format should fail."""
        result = FieldValidator.validate_member_id("12345")
        assert result.is_valid is False
        assert result.format_valid is False
        assert len(result.errors) > 0

    def test_invalid_length(self):
        """Invalid length should fail."""
        result = FieldValidator.validate_member_id("M123")
        assert result.is_valid is False
        assert result.format_valid is False
        assert len(result.errors) > 0

        result = FieldValidator.validate_member_id("M12345678901")
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_invalid_characters(self):
        """Non-alphanumeric characters should fail."""
        result = FieldValidator.validate_member_id("M123-5")
        assert result.is_valid is False
        assert result.format_valid is False
        assert len(result.errors) > 0

        result = FieldValidator.validate_member_id("M123 5")
        assert result.is_valid is False

    def test_none_value(self):
        """None should fail."""
        result = FieldValidator.validate_member_id(None)
        assert result.is_valid is False
        assert result.format_valid is False
        assert any("required" in err.lower() for err in result.errors)

    def test_empty_string(self):
        """Empty string should fail."""
        result = FieldValidator.validate_member_id("")
        assert result.is_valid is False
        assert result.format_valid is False
        assert any("required" in err.lower() for err in result.errors)

    def test_whitespace_only(self):
        """Whitespace-only should fail."""
        result = FieldValidator.validate_member_id("   ")
        assert result.is_valid is False
        assert len(result.errors) > 0


class TestMemberNameValidator:
    """Test member_name validation."""

    def test_valid_names(self):
        """Valid member names should pass."""
        result = FieldValidator.validate_member_name("John Doe")
        assert result.is_valid is True
        assert len(result.errors) == 0

        result = FieldValidator.validate_member_name("Ahmad bin Abdullah")
        assert result.is_valid is True

        result = FieldValidator.validate_member_name("Siti binti Rahman")
        assert result.is_valid is True

    def test_single_name_with_particle(self):
        """Single name with Malaysian particle should pass with warning."""
        result = FieldValidator.validate_member_name("Ahmad bin")
        assert result.is_valid is True
        # May have warnings but should be valid

    def test_single_name_without_particle(self):
        """Single name without particle should warn."""
        result = FieldValidator.validate_member_name("Ahmad")
        assert result.is_valid is True
        assert result.suspicious is True
        assert len(result.warnings) > 0

    def test_min_length(self):
        """Names too short should fail."""
        result = FieldValidator.validate_member_name("A")
        assert result.is_valid is False
        assert result.format_valid is False
        assert len(result.errors) > 0

    def test_max_length(self):
        """Names too long should fail."""
        long_name = "A" * 101
        result = FieldValidator.validate_member_name(long_name)
        assert result.is_valid is False
        assert result.format_valid is False
        assert len(result.errors) > 0

    def test_none_value(self):
        """None should fail."""
        result = FieldValidator.validate_member_name(None)
        assert result.is_valid is False
        assert result.format_valid is False
        assert any("required" in err.lower() for err in result.errors)

    def test_empty_string(self):
        """Empty string should fail."""
        result = FieldValidator.validate_member_name("")
        assert result.is_valid is False
        assert any("required" in err.lower() for err in result.errors)


class TestAmountValidator:
    """Test amount validation."""

    def test_valid_amounts(self):
        """Valid amounts should pass."""
        result = FieldValidator.validate_amount(100.00)
        assert result.is_valid is True
        assert result.range_valid is True
        assert len(result.errors) == 0

        result = FieldValidator.validate_amount(1.00)
        assert result.is_valid is True

        result = FieldValidator.validate_amount(9999.99)
        assert result.is_valid is True

    def test_zero_amount(self):
        """Zero amount should fail."""
        result = FieldValidator.validate_amount(0.00)
        assert result.is_valid is False
        assert result.range_valid is False
        assert len(result.errors) > 0

    def test_negative_amount(self):
        """Negative amount should fail."""
        result = FieldValidator.validate_amount(-50.00)
        assert result.is_valid is False
        assert result.range_valid is False
        assert len(result.errors) > 0

    def test_max_amount_exceeded(self):
        """Amount exceeding max should fail."""
        result = FieldValidator.validate_amount(1_000_001.00)
        assert result.is_valid is False
        assert result.range_valid is False
        assert len(result.errors) > 0

    def test_suspicious_amount(self):
        """High amounts should be flagged as suspicious."""
        result = FieldValidator.validate_amount(15_000.00)
        assert result.is_valid is True
        assert result.suspicious is True
        assert len(result.warnings) > 0

    def test_none_value(self):
        """None should fail."""
        result = FieldValidator.validate_amount(None)
        assert result.is_valid is False
        assert result.range_valid is False
        assert any("required" in err.lower() for err in result.errors)


class TestServiceDateValidator:
    """Test service_date validation."""

    def test_valid_dates(self):
        """Valid dates should pass."""
        result = FieldValidator.validate_service_date(datetime.now())
        assert result.is_valid is True
        assert result.range_valid is True
        assert len(result.errors) == 0

        yesterday = datetime.now() - timedelta(days=1)
        result = FieldValidator.validate_service_date(yesterday)
        assert result.is_valid is True

        last_month = datetime.now() - timedelta(days=30)
        result = FieldValidator.validate_service_date(last_month)
        assert result.is_valid is True

    def test_future_date(self):
        """Future dates should fail."""
        future_date = datetime.now() + timedelta(days=1)
        result = FieldValidator.validate_service_date(future_date)
        assert result.is_valid is False
        assert result.range_valid is False
        assert len(result.errors) > 0

    def test_date_too_old(self):
        """Dates older than 2 years should warn."""
        old_date = datetime.now() - timedelta(days=731)
        result = FieldValidator.validate_service_date(old_date)
        assert result.is_valid is True
        assert result.suspicious is True
        assert len(result.warnings) > 0

    def test_date_before_1900(self):
        """Dates before 1900 should fail."""
        old_date = datetime(1899, 12, 31)
        result = FieldValidator.validate_service_date(old_date)
        assert result.is_valid is False
        assert result.range_valid is False
        assert len(result.errors) > 0

    def test_none_value(self):
        """None should fail."""
        result = FieldValidator.validate_service_date(None)
        assert result.is_valid is False
        assert result.range_valid is False
        assert any("required" in err.lower() for err in result.errors)


class TestReceiptNumberValidator:
    """Test receipt_number validation."""

    def test_valid_receipt_numbers(self):
        """Valid receipt numbers should pass."""
        result = FieldValidator.validate_receipt_number("RCP-001")
        assert result.is_valid is True
        assert result.format_valid is True
        assert len(result.errors) == 0

        result = FieldValidator.validate_receipt_number("INV12345")
        assert result.is_valid is True

        result = FieldValidator.validate_receipt_number("REC/2024/001")
        assert result.is_valid is True

        result = FieldValidator.validate_receipt_number("12345")
        assert result.is_valid is True

    def test_min_length(self):
        """Receipt numbers too short should fail."""
        result = FieldValidator.validate_receipt_number("12")
        assert result.is_valid is False
        assert result.format_valid is False
        assert len(result.errors) > 0

    def test_max_length(self):
        """Receipt numbers too long should fail."""
        long_number = "A" * 21
        result = FieldValidator.validate_receipt_number(long_number)
        assert result.is_valid is False
        assert result.format_valid is False
        assert len(result.errors) > 0

    def test_invalid_characters(self):
        """Receipt numbers with invalid characters should fail."""
        result = FieldValidator.validate_receipt_number("RCP@001")
        assert result.is_valid is False
        assert result.format_valid is False
        assert len(result.errors) > 0

        result = FieldValidator.validate_receipt_number("RCP 001")
        assert result.is_valid is False

    def test_none_value(self):
        """None should fail."""
        result = FieldValidator.validate_receipt_number(None)
        assert result.is_valid is False
        assert result.format_valid is False
        assert any("required" in err.lower() for err in result.errors)


class TestProviderNameValidator:
    """Test provider_name validation."""

    def test_valid_names(self):
        """Valid provider names should pass."""
        result = FieldValidator.validate_provider_name("Klinik Dr. Ahmad")
        assert result.is_valid is True
        assert len(result.errors) == 0

        result = FieldValidator.validate_provider_name("Hospital Pantai")
        assert result.is_valid is True

        result = FieldValidator.validate_provider_name("Dr. Lee Medical Centre")
        assert result.is_valid is True

        result = FieldValidator.validate_provider_name("Farmasi Kesihatan")
        assert result.is_valid is True

    def test_min_length(self):
        """Names too short should fail."""
        result = FieldValidator.validate_provider_name("Dr")
        assert result.is_valid is False
        assert result.format_valid is False
        assert len(result.errors) > 0

    def test_max_length(self):
        """Names too long should fail."""
        long_name = "A" * 201
        result = FieldValidator.validate_provider_name(long_name)
        assert result.is_valid is False
        assert result.format_valid is False
        assert len(result.errors) > 0

    def test_missing_keywords(self):
        """Names without healthcare keywords should warn."""
        result = FieldValidator.validate_provider_name("ABC Company")
        assert result.is_valid is True
        assert result.suspicious is True
        assert len(result.warnings) > 0

    def test_none_value(self):
        """None should fail."""
        result = FieldValidator.validate_provider_name(None)
        assert result.is_valid is False
        assert result.format_valid is False
        assert any("required" in err.lower() for err in result.errors)

    def test_empty_string(self):
        """Empty string should fail."""
        result = FieldValidator.validate_provider_name("")
        assert result.is_valid is False
        assert any("required" in err.lower() for err in result.errors)


class TestValidateAllFields:
    """Test validate_all_fields method."""

    def test_all_valid_fields(self):
        """All valid fields should pass."""
        claim_data = {
            'member_id': 'M12345',
            'member_name': 'John Doe',
            'total_amount': 100.00,
            'service_date': datetime.now(),
            'receipt_number': 'RCP-001',
            'provider_name': 'Klinik Dr. Ahmad'
        }
        results = FieldValidator.validate_all_fields(claim_data)

        assert len(results) == 6
        assert all(r.is_valid for r in results.values())
        assert 'member_id' in results
        assert 'member_name' in results
        assert 'total_amount' in results
        assert 'service_date' in results
        assert 'receipt_number' in results
        assert 'provider_name' in results

    def test_missing_required_fields(self):
        """Missing required fields should fail."""
        claim_data = {
            'member_id': 'M12345',
            # Missing other required fields
        }
        results = FieldValidator.validate_all_fields(claim_data)

        assert len(results) == 6
        # Only member_id should be valid
        assert results['member_id'].is_valid is True
        assert results['member_name'].is_valid is False
        assert results['total_amount'].is_valid is False
        assert results['service_date'].is_valid is False
        assert results['receipt_number'].is_valid is False
        assert results['provider_name'].is_valid is False

    def test_invalid_field_values(self):
        """Invalid field values should fail validation."""
        claim_data = {
            'member_id': 'INVALID',
            'member_name': 'A',
            'total_amount': -50.00,
            'service_date': datetime.now() + timedelta(days=1),
            'receipt_number': 'AB',
            'provider_name': 'XY'
        }
        results = FieldValidator.validate_all_fields(claim_data)

        assert len(results) == 6
        assert all(not r.is_valid for r in results.values())

    def test_suspicious_values(self):
        """Suspicious values should be flagged."""
        claim_data = {
            'member_id': 'M12345',
            'member_name': 'Ahmad',  # Single name
            'total_amount': 15000.00,  # High amount
            'service_date': datetime.now() - timedelta(days=800),  # Old date
            'receipt_number': 'RCP-001',
            'provider_name': 'ABC Shop'  # No healthcare keywords
        }
        results = FieldValidator.validate_all_fields(claim_data)

        # All should be valid but some should have warnings
        assert all(r.is_valid for r in results.values())

        # Check for suspicious flags
        suspicious_count = sum(1 for r in results.values() if r.suspicious)
        assert suspicious_count > 0

        # Check for warnings
        warning_count = sum(len(r.warnings) for r in results.values())
        assert warning_count > 0
