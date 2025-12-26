"""
Unit tests for email subject parsing.

Tests member ID extraction, amount extraction, receipt number extraction,
provider name extraction, confidence scoring, and edge cases.
"""

import pytest
from src.services.email_parser import SubjectParser, ExtractedField


class TestSubjectParserMemberID:
    """Test member ID extraction from email subject."""

    @pytest.fixture
    def parser(self):
        """Create SubjectParser instance."""
        return SubjectParser()

    def test_extract_member_id_standard_format(self, parser):
        """Test extraction of standard Member ID format."""
        subject = "Claim for Member ID: M12345"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "M12345"
        assert result['member_id'].confidence >= 0.85

    def test_extract_member_id_policy_format(self, parser):
        """Test extraction of Policy number format."""
        subject = "Policy ABC123456 - Medical Claim"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "ABC123456"
        assert result['member_id'].confidence >= 0.75

    def test_extract_member_id_patient_format(self, parser):
        """Test extraction of Patient ID format."""
        subject = "Patient ID: XYZ789 Receipt"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "XYZ789"
        assert result['member_id'].confidence >= 0.80

    @pytest.mark.parametrize("subject,expected_id", [
        ("Member M12345", "M12345"),
        ("Policy ABC123456", "ABC123456"),
        ("Patient ID: XYZ789", "XYZ789"),
        ("ID M-2024-001", "M-2024-001"),
        ("Card No: CN98765", "CN98765"),
        ("Claim #C54321", "C54321"),
        ("Member: M00001", "M00001"),
        ("Policy No ABC-DEF-123", "ABC-DEF-123"),
        ("Patient XYZ-456", "XYZ-456"),
        ("ID: 1234567890", "1234567890"),
    ])
    def test_member_id_variations(self, parser, subject, expected_id):
        """Test various member ID formats."""
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == expected_id
        assert result['member_id'].confidence > 0.0

    def test_member_id_not_found(self, parser):
        """Test when no member ID is found."""
        subject = "Medical Receipt - No ID"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value is None
        assert result['member_id'].confidence == 0.0

    def test_member_id_malaysian_ic_format(self, parser):
        """Test extraction of Malaysian IC number as member ID."""
        subject = "Claim for IC: 901231-12-3456"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "901231-12-3456"
        assert result['member_id'].confidence >= 0.70


class TestSubjectParserAmount:
    """Test amount extraction from email subject."""

    @pytest.fixture
    def parser(self):
        """Create SubjectParser instance."""
        return SubjectParser()

    def test_extract_amount_simple(self, parser):
        """Test extraction of simple amount."""
        subject = "Receipt RM150.00"
        result = parser.extract_from_subject(subject)

        assert result['amount'].value == "150.00"
        assert result['amount'].confidence >= 0.85

    def test_extract_amount_with_commas(self, parser):
        """Test extraction of amount with thousand separators."""
        subject = "Receipt RM1,500.50"
        result = parser.extract_from_subject(subject)

        assert result['amount'].value == "1500.50"
        assert result['amount'].confidence >= 0.85

    def test_extract_amount_no_decimal(self, parser):
        """Test extraction of amount without decimal."""
        subject = "Total RM500"
        result = parser.extract_from_subject(subject)

        assert result['amount'].value in ["500", "500.00"]
        assert result['amount'].confidence >= 0.80

    @pytest.mark.parametrize("subject,expected_amount", [
        ("RM150.00", "150.00"),
        ("RM 250.50", "250.50"),
        ("Total: RM1,234.56", "1234.56"),
        ("Amount RM 999", "999"),
        ("Claim RM5,000.00", "5000.00"),
        ("Receipt: RM100.50", "100.50"),
        ("RM10,500.75", "10500.75"),
        ("Pay RM 1500.00", "1500.00"),
    ])
    def test_amount_variations(self, parser, subject, expected_amount):
        """Test various amount formats."""
        result = parser.extract_from_subject(subject)

        assert result['amount'].value == expected_amount or \
               result['amount'].value == expected_amount.rstrip('0').rstrip('.')

    def test_amount_not_found(self, parser):
        """Test when no amount is found."""
        subject = "Medical Receipt"
        result = parser.extract_from_subject(subject)

        assert result['amount'].value is None
        assert result['amount'].confidence == 0.0

    def test_amount_multiple_values(self, parser):
        """Test when multiple amounts present - should extract first/largest."""
        subject = "Receipt RM150.00 GST RM9.00 Total RM159.00"
        result = parser.extract_from_subject(subject)

        # Should extract one of the amounts, preferably total
        assert result['amount'].value in ["150.00", "159.00", "9.00"]
        assert result['amount'].confidence > 0.0

    def test_amount_sen_only(self, parser):
        """Test extraction of small amounts (sen only)."""
        subject = "Claim RM0.50"
        result = parser.extract_from_subject(subject)

        assert result['amount'].value in ["0.50", "0.5"]


class TestSubjectParserReceiptNumber:
    """Test receipt number extraction from email subject."""

    @pytest.fixture
    def parser(self):
        """Create SubjectParser instance."""
        return SubjectParser()

    def test_extract_receipt_number_standard(self, parser):
        """Test extraction of standard receipt number."""
        subject = "Receipt #12345"
        result = parser.extract_from_subject(subject)

        assert result['receipt_number'].value == "12345"
        assert result['receipt_number'].confidence >= 0.80

    def test_extract_receipt_number_with_prefix(self, parser):
        """Test extraction of receipt number with prefix."""
        subject = "Receipt No: RCP-2024-001"
        result = parser.extract_from_subject(subject)

        assert result['receipt_number'].value == "RCP-2024-001"
        assert result['receipt_number'].confidence >= 0.85

    @pytest.mark.parametrize("subject,expected_number", [
        ("Receipt #12345", "12345"),
        ("Receipt No: RCP001", "RCP001"),
        ("Invoice INV-2024-123", "INV-2024-123"),
        ("Bill #B54321", "B54321"),
        ("Receipt: 987654", "987654"),
        ("Rcpt #RC123456", "RC123456"),
        ("Doc No: DOC-001", "DOC-001"),
    ])
    def test_receipt_number_variations(self, parser, subject, expected_number):
        """Test various receipt number formats."""
        result = parser.extract_from_subject(subject)

        assert result['receipt_number'].value == expected_number

    def test_receipt_number_not_found(self, parser):
        """Test when no receipt number is found."""
        subject = "Medical Claim"
        result = parser.extract_from_subject(subject)

        assert result['receipt_number'].value is None
        assert result['receipt_number'].confidence == 0.0


class TestSubjectParserProviderName:
    """Test provider name extraction from email subject."""

    @pytest.fixture
    def parser(self):
        """Create SubjectParser instance."""
        return SubjectParser()

    def test_extract_provider_name_clinic(self, parser):
        """Test extraction of clinic name."""
        subject = "Claim from ABC Clinic"
        result = parser.extract_from_subject(subject)

        assert result['provider_name'].value == "ABC Clinic"
        assert result['provider_name'].confidence >= 0.70

    def test_extract_provider_name_hospital(self, parser):
        """Test extraction of hospital name."""
        subject = "Receipt - XYZ Hospital"
        result = parser.extract_from_subject(subject)

        assert result['provider_name'].value == "XYZ Hospital"
        assert result['provider_name'].confidence >= 0.75

    @pytest.mark.parametrize("subject,expected_name", [
        ("Claim from ABC Clinic", "ABC Clinic"),
        ("Receipt - XYZ Hospital", "XYZ Hospital"),
        ("Dr. Ahmad Medical Centre", "Dr. Ahmad Medical Centre"),
        ("KPJ Healthcare Sdn Bhd", "KPJ Healthcare Sdn Bhd"),
        ("Pantai Hospital Kuala Lumpur", "Pantai Hospital Kuala Lumpur"),
        ("Klinik Kesihatan", "Klinik Kesihatan"),
    ])
    def test_provider_name_variations(self, parser, subject, expected_name):
        """Test various provider name formats."""
        result = parser.extract_from_subject(subject)

        assert expected_name in result['provider_name'].value or \
               result['provider_name'].value in expected_name

    def test_provider_name_not_found(self, parser):
        """Test when no provider name is found."""
        subject = "Medical Receipt #12345"
        result = parser.extract_from_subject(subject)

        assert result['provider_name'].value is None or \
               result['provider_name'].confidence < 0.5


class TestSubjectParserConfidenceScoring:
    """Test confidence scoring logic."""

    @pytest.fixture
    def parser(self):
        """Create SubjectParser instance."""
        return SubjectParser()

    def test_high_confidence_all_fields(self, parser):
        """Test high confidence when all fields are found."""
        subject = "Claim Member M12345 Receipt #RCP001 RM150.00 - ABC Clinic"
        result = parser.extract_from_subject(subject)

        # Should have high confidence for most fields
        assert result['member_id'].confidence >= 0.80
        assert result['receipt_number'].confidence >= 0.80
        assert result['amount'].confidence >= 0.80

    def test_low_confidence_ambiguous(self, parser):
        """Test low confidence with ambiguous data."""
        subject = "Claim 12345 150"
        result = parser.extract_from_subject(subject)

        # Ambiguous - could be ID or receipt number, could be amount
        # At least one field should have lower confidence
        confidences = [
            result['member_id'].confidence,
            result['receipt_number'].confidence,
            result['amount'].confidence
        ]
        assert min(confidences) < 0.80

    def test_confidence_with_keywords(self, parser):
        """Test higher confidence when keywords are present."""
        subject_with_keyword = "Member ID: M12345"
        subject_without_keyword = "M12345"

        result_with = parser.extract_from_subject(subject_with_keyword)
        result_without = parser.extract_from_subject(subject_without_keyword)

        # With keyword should have higher or equal confidence
        assert result_with['member_id'].confidence >= result_without['member_id'].confidence


class TestSubjectParserEdgeCases:
    """Test edge cases for subject parsing."""

    @pytest.fixture
    def parser(self):
        """Create SubjectParser instance."""
        return SubjectParser()

    def test_empty_subject(self, parser):
        """Test parsing of empty subject."""
        result = parser.extract_from_subject("")

        assert all(field.value is None for field in result.values())
        assert all(field.confidence == 0.0 for field in result.values())

    def test_none_subject(self, parser):
        """Test parsing of None subject."""
        result = parser.extract_from_subject(None)

        assert all(field.value is None for field in result.values())

    def test_very_long_subject(self, parser):
        """Test parsing of very long subject."""
        subject = "A" * 500 + " Member M12345 " + "B" * 500
        result = parser.extract_from_subject(subject)

        # Should still extract member ID
        assert result['member_id'].value == "M12345"

    def test_special_characters_in_subject(self, parser):
        """Test subject with special characters."""
        subject = "Claim: M12345 | RM150.00 | Receipt #123 | @ABC Clinic"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "M12345"
        assert result['amount'].value == "150.00"
        assert result['receipt_number'].value == "123"

    def test_unicode_characters(self, parser):
        """Test subject with unicode characters."""
        subject = "Tuntutan Member M12345 RM150.00 病人 患者"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "M12345"
        assert result['amount'].value == "150.00"

    def test_case_insensitive_extraction(self, parser):
        """Test that extraction is case insensitive."""
        subject_upper = "MEMBER M12345 RECEIPT RM150.00"
        subject_lower = "member m12345 receipt rm150.00"
        subject_mixed = "MeMbEr M12345 ReCeIpT rM150.00"

        result_upper = parser.extract_from_subject(subject_upper)
        result_lower = parser.extract_from_subject(subject_lower)
        result_mixed = parser.extract_from_subject(subject_mixed)

        assert result_upper['member_id'].value == result_lower['member_id'].value == result_mixed['member_id'].value

    def test_malformed_amounts(self, parser):
        """Test handling of malformed amounts."""
        malformed_subjects = [
            "RM..150",
            "RM1,50",
            "RM1.2.3",
            "RM",
        ]

        for subject in malformed_subjects:
            result = parser.extract_from_subject(subject)
            # Should either extract correctly or return None
            assert result['amount'].value is None or \
                   isinstance(result['amount'].value, str)

    def test_multiple_member_ids(self, parser):
        """Test when multiple potential member IDs are present."""
        subject = "Member M12345 Policy ABC123 Patient XYZ789"
        result = parser.extract_from_subject(subject)

        # Should extract one of them
        assert result['member_id'].value in ["M12345", "ABC123", "XYZ789"]

    def test_malay_language_keywords(self, parser):
        """Test extraction with Malay keywords."""
        subject = "Tuntutan Ahli M12345 Resit RM150.00"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "M12345"
        assert result['amount'].value == "150.00"

    def test_chinese_language_content(self, parser):
        """Test subject with Chinese characters."""
        subject = "索赔 Member M12345 金额 RM150.00"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "M12345"
        assert result['amount'].value == "150.00"

    def test_mixed_currency_symbols(self, parser):
        """Test when multiple currency symbols present."""
        subject = "Claim USD$50.00 RM150.00"
        result = parser.extract_from_subject(subject)

        # Should prefer RM amount
        assert result['amount'].value in ["50.00", "150.00"]

    def test_date_not_confused_with_id(self, parser):
        """Test that dates are not confused with member IDs."""
        subject = "Claim dated 12/12/2024 Member M12345"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "M12345"
        assert "12/12/2024" not in str(result['member_id'].value)

    def test_email_address_not_confused(self, parser):
        """Test that email addresses don't interfere."""
        subject = "Claim from user@example.com Member M12345"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "M12345"


class TestSubjectParserComprehensive:
    """Comprehensive integration tests for subject parser."""

    @pytest.fixture
    def parser(self):
        """Create SubjectParser instance."""
        return SubjectParser()

    def test_real_world_subject_1(self, parser):
        """Test realistic subject line format 1."""
        subject = "Medical Claim - Member ID: M12345 - Receipt #RCP2024001 - RM150.00"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "M12345"
        assert result['receipt_number'].value == "RCP2024001"
        assert result['amount'].value == "150.00"

    def test_real_world_subject_2(self, parser):
        """Test realistic subject line format 2."""
        subject = "Fwd: Claim from Klinik Kesihatan - Policy ABC123456 - RM1,250.50"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "ABC123456"
        assert result['amount'].value == "1250.50"
        assert "Klinik" in result['provider_name'].value or \
               result['provider_name'].value is None

    def test_real_world_subject_3(self, parser):
        """Test realistic subject line format 3."""
        subject = "RE: Medical Receipt - Patient XYZ789 - Total: RM350.00"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "XYZ789"
        assert result['amount'].value == "350.00"

    def test_minimal_subject(self, parser):
        """Test minimal information in subject."""
        subject = "Claim M12345"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "M12345"

    def test_comprehensive_subject(self, parser):
        """Test subject with all possible fields."""
        subject = "Claim - Member M12345 - ABC Hospital - Receipt #RCP001 - Date: 15/12/2024 - Total: RM1,500.00"
        result = parser.extract_from_subject(subject)

        assert result['member_id'].value == "M12345"
        assert result['receipt_number'].value == "RCP001"
        assert result['amount'].value == "1500.00"
        assert result['provider_name'].value is not None
