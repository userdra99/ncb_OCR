"""
Unit tests for email body parsing.

Tests required field extraction, Malaysian date parsing, Malaysian currency parsing,
multi-language support, and missing field handling.
"""

import pytest
from datetime import datetime
from src.services.email_parser import BodyParser, ExtractedField


class TestBodyParserRequiredFields:
    """Test extraction of all required fields from email body."""

    @pytest.fixture
    def parser(self):
        """Create BodyParser instance."""
        return BodyParser()

    def test_extract_all_required_fields(self, parser):
        """Test extraction of all required fields."""
        body = """
        Member ID: M12345
        Member Name: Ali bin Abu
        Provider Name: ABC Medical Centre
        Service Date: 15/12/2024
        Receipt Number: RCP-2024-001
        Total Amount: RM1,500.50
        """

        result = parser.extract_from_body(body)

        assert result['member_id'].value == "M12345"
        assert result['member_name'].value == "Ali bin Abu"
        assert result['provider_name'].value == "ABC Medical Centre"
        assert result['service_date'].value in ["15/12/2024", "2024-12-15"]
        assert result['receipt_number'].value == "RCP-2024-001"
        assert result['total_amount'].value == "1500.50"

    def test_extract_member_id(self, parser):
        """Test member ID extraction."""
        body = "Patient Member ID: M12345"
        result = parser.extract_from_body(body)

        assert result['member_id'].value == "M12345"
        assert result['member_id'].confidence >= 0.80

    def test_extract_member_name(self, parser):
        """Test member name extraction."""
        body = """
        Patient Name: Dr. Ahmad bin Abdullah
        """
        result = parser.extract_from_body(body)

        assert result['member_name'].value == "Dr. Ahmad bin Abdullah"
        assert result['member_name'].confidence >= 0.75

    def test_extract_provider_name(self, parser):
        """Test provider name extraction."""
        body = """
        Clinic: ABC Medical Centre Sdn Bhd
        """
        result = parser.extract_from_body(body)

        assert "ABC Medical Centre" in result['provider_name'].value
        assert result['provider_name'].confidence >= 0.70


class TestBodyParserMalaysianDates:
    """Test Malaysian date format parsing."""

    @pytest.fixture
    def parser(self):
        """Create BodyParser instance."""
        return BodyParser()

    def test_parse_date_dd_mm_yyyy_slash(self, parser):
        """Test DD/MM/YYYY format."""
        body = "Date of Service: 15/12/2024"
        result = parser.extract_from_body(body)

        assert result['service_date'].value in ["15/12/2024", "2024-12-15"]
        assert result['service_date'].confidence >= 0.85

    def test_parse_date_dd_mm_yyyy_dash(self, parser):
        """Test DD-MM-YYYY format."""
        body = "Service Date: 15-12-2024"
        result = parser.extract_from_body(body)

        assert result['service_date'].value in ["15-12-2024", "15/12/2024", "2024-12-15"]
        assert result['service_date'].confidence >= 0.85

    def test_parse_date_dd_mm_yy(self, parser):
        """Test DD/MM/YY format."""
        body = "Date: 15/12/24"
        result = parser.extract_from_body(body)

        # Should interpret as 2024
        assert "15" in result['service_date'].value
        assert "12" in result['service_date'].value
        assert result['service_date'].confidence >= 0.75

    @pytest.mark.parametrize("date_str,expected_day,expected_month", [
        ("15/12/2024", "15", "12"),
        ("01/01/2024", "01", "01"),
        ("31-12-2024", "31", "12"),
        ("15.12.2024", "15", "12"),
        ("15 Dec 2024", "15", "12"),
        ("15 December 2024", "15", "12"),
    ])
    def test_date_format_variations(self, parser, date_str, expected_day, expected_month):
        """Test various date format variations."""
        body = f"Service Date: {date_str}"
        result = parser.extract_from_body(body)

        assert expected_day in result['service_date'].value
        assert expected_month in result['service_date'].value or \
               "Dec" in result['service_date'].value or \
               "12" in result['service_date'].value

    def test_malay_month_names(self, parser):
        """Test Malay month names."""
        body = "Tarikh: 15 Disember 2024"
        result = parser.extract_from_body(body)

        # Should recognize Malay month name
        assert result['service_date'].value is not None
        assert result['service_date'].confidence > 0.0

    def test_date_range_extract_first(self, parser):
        """Test extraction when date range is present."""
        body = "Service Period: 15/12/2024 to 20/12/2024"
        result = parser.extract_from_body(body)

        # Should extract first date
        assert "15" in result['service_date'].value
        assert "12" in result['service_date'].value

    def test_invalid_date_handling(self, parser):
        """Test handling of invalid dates."""
        body = "Date: 32/13/2024"  # Invalid date
        result = parser.extract_from_body(body)

        # Should either not extract or mark low confidence
        assert result['service_date'].value is None or \
               result['service_date'].confidence < 0.50


class TestBodyParserMalaysianCurrency:
    """Test Malaysian currency format parsing."""

    @pytest.fixture
    def parser(self):
        """Create BodyParser instance."""
        return BodyParser()

    def test_parse_amount_rm_prefix(self, parser):
        """Test RM prefix format."""
        body = "Total: RM1,500.50"
        result = parser.extract_from_body(body)

        assert result['total_amount'].value == "1500.50"
        assert result['total_amount'].confidence >= 0.85

    def test_parse_amount_rm_space(self, parser):
        """Test RM with space format."""
        body = "Amount: RM 2,345.00"
        result = parser.extract_from_body(body)

        assert result['total_amount'].value == "2345.00"

    def test_parse_amount_ringgit(self, parser):
        """Test Ringgit keyword."""
        body = "Jumlah: Ringgit 500.00"
        result = parser.extract_from_body(body)

        assert result['total_amount'].value in ["500.00", "500"]

    @pytest.mark.parametrize("amount_str,expected", [
        ("RM150.00", "150.00"),
        ("RM1,500.50", "1500.50"),
        ("RM10,000.00", "10000.00"),
        ("RM 250.00", "250.00"),
        ("MYR 300.00", "300.00"),
        ("Ringgit 400.00", "400.00"),
        ("RM1500", "1500"),
    ])
    def test_currency_format_variations(self, parser, amount_str, expected):
        """Test various currency format variations."""
        body = f"Total: {amount_str}"
        result = parser.extract_from_body(body)

        # Remove trailing zeros for comparison
        actual = result['total_amount'].value.rstrip('0').rstrip('.')
        expected_norm = expected.rstrip('0').rstrip('.')
        assert actual == expected_norm or result['total_amount'].value == expected

    def test_extract_gst_amount(self, parser):
        """Test GST amount extraction."""
        body = """
        Subtotal: RM100.00
        GST (6%): RM6.00
        Total: RM106.00
        """
        result = parser.extract_from_body(body)

        assert result.get('gst_amount') is not None or \
               'gst' in str(result).lower()

    def test_extract_sst_amount(self, parser):
        """Test SST amount extraction."""
        body = """
        Subtotal: RM100.00
        SST (10%): RM10.00
        Total: RM110.00
        """
        result = parser.extract_from_body(body)

        # SST should be captured if field exists
        assert result.get('sst_amount') is not None or \
               result['total_amount'].value == "110.00"


class TestBodyParserOptionalFields:
    """Test extraction of optional fields."""

    @pytest.fixture
    def parser(self):
        """Create BodyParser instance."""
        return BodyParser()

    def test_extract_provider_address(self, parser):
        """Test provider address extraction."""
        body = """
        Clinic Name: ABC Medical Centre
        Address: 123, Jalan Bukit Bintang,
                 55100 Kuala Lumpur
        """
        result = parser.extract_from_body(body)

        assert result.get('provider_address') is not None
        assert "Jalan" in result['provider_address'].value or \
               "Kuala Lumpur" in result['provider_address'].value

    def test_extract_itemized_charges(self, parser):
        """Test itemized charges extraction."""
        body = """
        Services:
        - Consultation: RM50.00
        - X-Ray: RM100.00
        - Medicine: RM200.00
        Total: RM350.00
        """
        result = parser.extract_from_body(body)

        # Should extract itemized charges if field exists
        itemized = result.get('itemized_charges')
        assert itemized is not None or result['total_amount'].value == "350.00"


class TestBodyParserMultiLanguage:
    """Test multi-language support."""

    @pytest.fixture
    def parser(self):
        """Create BodyParser instance."""
        return BodyParser()

    def test_extract_malay_keywords(self, parser):
        """Test extraction with Malay keywords."""
        body = """
        Nama Pesakit: Ahmad bin Ali
        Tarikh Perkhidmatan: 15/12/2024
        Jumlah: RM150.00
        """
        result = parser.extract_from_body(body)

        assert result['member_name'].value == "Ahmad bin Ali"
        assert "15" in result['service_date'].value
        assert result['total_amount'].value == "150.00"

    def test_extract_mixed_english_malay(self, parser):
        """Test extraction with mixed English and Malay."""
        body = """
        Patient Name: Siti binti Abdullah
        Tarikh: 15/12/2024
        Total Amount: RM200.00
        Klinik: ABC Medical Centre
        """
        result = parser.extract_from_body(body)

        assert "Siti" in result['member_name'].value
        assert result['total_amount'].value == "200.00"

    def test_extract_chinese_characters(self, parser):
        """Test extraction with Chinese characters."""
        body = """
        病人姓名: 李明
        Patient Name: Lee Ming
        Date: 15/12/2024
        Total: RM150.00
        """
        result = parser.extract_from_body(body)

        # Should extract English name or both
        assert "Lee Ming" in result['member_name'].value or \
               "李明" in result['member_name'].value

    def test_extract_tamil_characters(self, parser):
        """Test extraction with Tamil characters."""
        body = """
        Patient: ராஜா / Raja
        Date: 15/12/2024
        Amount: RM150.00
        """
        result = parser.extract_from_body(body)

        # Should extract name in some form
        assert "Raja" in result['member_name'].value or \
               result['member_name'].value is not None


class TestBodyParserMissingFields:
    """Test handling of missing fields."""

    @pytest.fixture
    def parser(self):
        """Create BodyParser instance."""
        return BodyParser()

    def test_partial_information(self, parser):
        """Test when only some fields are present."""
        body = """
        Member ID: M12345
        Total: RM150.00
        """
        result = parser.extract_from_body(body)

        assert result['member_id'].value == "M12345"
        assert result['total_amount'].value == "150.00"
        assert result['member_name'].value is None
        assert result['service_date'].value is None

    def test_empty_body(self, parser):
        """Test empty email body."""
        result = parser.extract_from_body("")

        assert all(field.value is None for field in result.values())
        assert all(field.confidence == 0.0 for field in result.values())

    def test_none_body(self, parser):
        """Test None email body."""
        result = parser.extract_from_body(None)

        assert all(field.value is None for field in result.values())

    def test_no_relevant_information(self, parser):
        """Test body with no relevant information."""
        body = """
        Thank you for your email.
        We will process this shortly.
        Best regards,
        Support Team
        """
        result = parser.extract_from_body(body)

        # Should not extract false positives
        assert all(field.confidence < 0.70 or field.value is None
                  for field in result.values())


class TestBodyParserConfidenceScoring:
    """Test confidence scoring for body parsing."""

    @pytest.fixture
    def parser(self):
        """Create BodyParser instance."""
        return BodyParser()

    def test_high_confidence_with_labels(self, parser):
        """Test high confidence when field labels are present."""
        body = """
        Member ID: M12345
        Total Amount: RM150.00
        """
        result = parser.extract_from_body(body)

        assert result['member_id'].confidence >= 0.85
        assert result['total_amount'].confidence >= 0.85

    def test_lower_confidence_without_labels(self, parser):
        """Test lower confidence when extracting without clear labels."""
        body = "M12345 paid RM150.00 on 15/12/2024"
        result = parser.extract_from_body(body)

        # Should extract but with lower confidence
        if result['member_id'].value is not None:
            assert result['member_id'].confidence < 0.90


class TestBodyParserEdgeCases:
    """Test edge cases for body parsing."""

    @pytest.fixture
    def parser(self):
        """Create BodyParser instance."""
        return BodyParser()

    def test_very_long_body(self, parser):
        """Test parsing very long email body."""
        body = "A" * 10000 + "\nMember ID: M12345\n" + "B" * 10000
        result = parser.extract_from_body(body)

        assert result['member_id'].value == "M12345"

    def test_special_characters(self, parser):
        """Test body with special characters."""
        body = """
        Patient: O'Brien & Associates
        Amount: RM1,500.00 (USD$500)
        Address: #12-34, Tower A
        """
        result = parser.extract_from_body(body)

        assert "O'Brien" in result['member_name'].value
        assert result['total_amount'].value == "1500.00"

    def test_table_format(self, parser):
        """Test extraction from table-formatted text."""
        body = """
        | Field          | Value              |
        |----------------|-------------------|
        | Member ID      | M12345            |
        | Amount         | RM150.00          |
        | Date           | 15/12/2024        |
        """
        result = parser.extract_from_body(body)

        assert result['member_id'].value == "M12345"
        assert result['total_amount'].value == "150.00"

    def test_bullet_points(self, parser):
        """Test extraction from bullet-pointed text."""
        body = """
        • Member ID: M12345
        • Patient Name: Ali bin Abu
        • Amount: RM150.00
        • Date: 15/12/2024
        """
        result = parser.extract_from_body(body)

        assert result['member_id'].value == "M12345"
        assert "Ali" in result['member_name'].value

    def test_multiple_amounts_extract_total(self, parser):
        """Test extracting total when multiple amounts present."""
        body = """
        Subtotal: RM100.00
        Tax: RM10.00
        Total: RM110.00
        """
        result = parser.extract_from_body(body)

        # Should prefer "Total" labeled amount
        assert result['total_amount'].value == "110.00"

    def test_duplicate_fields_extract_first(self, parser):
        """Test when duplicate fields are present."""
        body = """
        Member ID: M12345
        Old Member ID: M00001
        """
        result = parser.extract_from_body(body)

        # Should extract one of them
        assert result['member_id'].value in ["M12345", "M00001"]


class TestBodyParserRealWorld:
    """Test real-world email body scenarios."""

    @pytest.fixture
    def parser(self):
        """Create BodyParser instance."""
        return BodyParser()

    def test_typical_clinic_receipt(self, parser):
        """Test typical clinic receipt format."""
        body = """
        ABC Medical Centre Sdn Bhd
        123, Jalan Bukit Bintang
        55100 Kuala Lumpur

        Receipt No: RCP-2024-001
        Date: 15/12/2024

        Patient Name: Ali bin Abu
        Member ID: M12345

        Services Rendered:
        - Consultation: RM50.00
        - Medicine: RM100.00

        Subtotal: RM150.00
        SST (10%): RM15.00
        Total: RM165.00

        Thank you for your visit.
        """
        result = parser.extract_from_body(body)

        assert result['member_id'].value == "M12345"
        assert "Ali bin Abu" in result['member_name'].value
        assert result['receipt_number'].value == "RCP-2024-001"
        assert result['service_date'].value in ["15/12/2024", "2024-12-15"]
        assert result['total_amount'].value == "165.00"
        assert "ABC Medical Centre" in result['provider_name'].value

    def test_minimal_receipt_info(self, parser):
        """Test minimal receipt with just key info."""
        body = """
        Attached is the receipt.

        Member: M12345
        Amount paid: RM150.00
        Date: 15/12/2024

        Thanks
        """
        result = parser.extract_from_body(body)

        assert result['member_id'].value == "M12345"
        assert result['total_amount'].value == "150.00"
        assert "15/12/2024" in result['service_date'].value or \
               "2024-12-15" in result['service_date'].value

    def test_forwarded_receipt_email(self, parser):
        """Test forwarded email with receipt info."""
        body = """
        ---------- Forwarded message ---------
        From: clinic@example.com
        Date: Mon, Dec 15, 2024
        Subject: Receipt

        Dear Patient,

        Your receipt details:
        Member ID: M12345
        Total Amount: RM150.00
        Service Date: 15/12/2024

        Regards,
        ABC Clinic
        """
        result = parser.extract_from_body(body)

        assert result['member_id'].value == "M12345"
        assert result['total_amount'].value == "150.00"
