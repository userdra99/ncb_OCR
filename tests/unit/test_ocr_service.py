"""
Unit tests for OCR Service

Tests extraction, data structuring, and confidence calculation
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


# These tests assume the following models exist in src/models/
# - ExtractedClaim, ExtractionResult, ConfidenceLevel
# - OCRResult (internal OCR result structure)


@pytest.mark.unit
@pytest.mark.ocr
class TestOCRService:
    """Test suite for OCR Service"""

    @pytest.fixture
    def ocr_service(self, mock_ocr_engine, mock_env):
        """Create OCR service instance with mocked dependencies."""
        # This will be implemented once src/services/ocr_service.py exists
        # For now, we define the test structure
        with patch('src.services.ocr_service.PaddleOCR', return_value=mock_ocr_engine):
            from src.services.ocr_service import OCRService
            from src.config.settings import OCRConfig

            config = OCRConfig()
            return OCRService(config)

    @pytest.mark.asyncio
    async def test_extract_text_from_image(self, ocr_service, test_data_dir):
        """
        Test basic text extraction from image

        Given: A receipt image file
        When: extract_text() is called
        Then: Raw OCR result with text blocks is returned
        """
        # Arrange
        test_image = test_data_dir / "sample_receipt.jpg"

        # Act
        result = await ocr_service.extract_text(test_image)

        # Assert
        assert result is not None
        assert hasattr(result, 'text_blocks')
        assert len(result.text_blocks) > 0
        assert all(hasattr(block, 'text') for block in result.text_blocks)
        assert all(hasattr(block, 'confidence') for block in result.text_blocks)

    @pytest.mark.asyncio
    async def test_extract_text_handles_rotation(self, ocr_service, test_data_dir):
        """
        Test that rotated images are handled correctly

        Given: A rotated receipt image
        When: extract_text() is called with use_angle_cls=True
        Then: Text is correctly extracted despite rotation
        """
        # Arrange
        rotated_image = test_data_dir / "rotated_receipt.jpg"

        # Act
        result = await ocr_service.extract_text(rotated_image)

        # Assert
        assert result is not None
        assert len(result.text_blocks) > 0
        # Should detect rotation and correct it
        assert any("Receipt" in block.text or "Total" in block.text
                  for block in result.text_blocks)

    @pytest.mark.asyncio
    async def test_extract_text_handles_pdf(self, ocr_service, test_data_dir):
        """
        Test PDF receipt extraction

        Given: A PDF receipt file
        When: extract_text() is called
        Then: PDF pages are converted to images and text extracted
        """
        # Arrange
        pdf_receipt = test_data_dir / "sample_receipt.pdf"

        # Act
        result = await ocr_service.extract_text(pdf_receipt)

        # Assert
        assert result is not None
        assert len(result.text_blocks) > 0

    @pytest.mark.asyncio
    async def test_extract_structured_data_complete(self, ocr_service, test_data_dir):
        """
        Test complete data extraction with all fields

        Given: A high-quality receipt with all required fields
        When: extract_structured_data() is called
        Then: All required fields are extracted with high confidence
        """
        # Arrange
        complete_receipt = test_data_dir / "complete_receipt.jpg"

        # Act
        result = await ocr_service.extract_structured_data(complete_receipt)

        # Assert
        assert result is not None
        assert result.claim is not None

        # Check required fields
        assert result.claim.member_id is not None
        assert result.claim.member_name is not None
        assert result.claim.provider_name is not None
        assert result.claim.service_date is not None
        assert result.claim.receipt_number is not None
        assert result.claim.total_amount is not None

        # Check confidence
        assert result.confidence_score >= 0.0
        assert result.confidence_score <= 1.0
        assert result.confidence_level in ["high", "medium", "low"]

    @pytest.mark.asyncio
    @pytest.mark.malaysian
    async def test_extract_malaysian_amount_format(self, ocr_service, malaysian_receipt_samples):
        """
        Test Malaysian currency format parsing

        Given: Receipt with "RM 150.00" format
        When: Amount is extracted
        Then: Correctly parses to 150.00
        """
        # Arrange
        receipt_text = malaysian_receipt_samples["english"]["text"]

        # Create mock image with this text
        with patch.object(ocr_service, 'extract_text') as mock_extract:
            mock_extract.return_value = MagicMock(raw_text=receipt_text)

            # Act
            result = await ocr_service.extract_structured_data(Path("/tmp/test.jpg"))

            # Assert
            assert result.claim.total_amount == 159.00
            assert result.claim.currency == "MYR"

    @pytest.mark.asyncio
    @pytest.mark.malaysian
    async def test_extract_malaysian_date_formats(self, ocr_service):
        """
        Test Malaysian date format parsing

        Given: Receipts with DD/MM/YYYY and DD-MM-YYYY formats
        When: Date is extracted
        Then: Correctly parsed to datetime
        """
        # Arrange
        test_cases = [
            ("15/12/2024", datetime(2024, 12, 15)),
            ("15-12-2024", datetime(2024, 12, 15)),
            ("01/01/2024", datetime(2024, 1, 1)),
        ]

        for date_str, expected_date in test_cases:
            # Act
            parsed = ocr_service._parse_date(date_str)

            # Assert
            assert parsed.date() == expected_date.date()

    @pytest.mark.asyncio
    async def test_extract_provider_name_and_address(self, ocr_service, malaysian_receipt_samples):
        """
        Test provider name and address extraction

        Given: Receipt with provider details at top
        When: Structured data is extracted
        Then: Provider name and address correctly identified
        """
        # Arrange
        receipt_text = malaysian_receipt_samples["english"]["text"]

        with patch.object(ocr_service, 'extract_text') as mock_extract:
            mock_extract.return_value = MagicMock(raw_text=receipt_text)

            # Act
            result = await ocr_service.extract_structured_data(Path("/tmp/test.jpg"))

            # Assert
            assert result.claim.provider_name == "City Medical Centre"
            assert "Main Street" in result.claim.provider_address
            assert "Kuala Lumpur" in result.claim.provider_address

    @pytest.mark.asyncio
    async def test_extract_itemized_charges(self, ocr_service, malaysian_receipt_samples):
        """
        Test itemized charge extraction

        Given: Receipt with line items
        When: Structured data is extracted
        Then: Itemized charges array populated
        """
        # Arrange
        receipt_text = malaysian_receipt_samples["english"]["text"]

        with patch.object(ocr_service, 'extract_text') as mock_extract:
            mock_extract.return_value = MagicMock(raw_text=receipt_text)

            # Act
            result = await ocr_service.extract_structured_data(Path("/tmp/test.jpg"))

            # Assert
            assert result.claim.itemized_charges is not None
            assert len(result.claim.itemized_charges) >= 2
            assert any(item["description"] == "Consultation" for item in result.claim.itemized_charges)
            assert any(item["amount"] == 80.00 for item in result.claim.itemized_charges)

    @pytest.mark.asyncio
    async def test_extract_gst_sst_amounts(self, ocr_service):
        """
        Test GST/SST extraction

        Given: Receipts with GST (old) or SST (current) tax
        When: Tax amounts extracted
        Then: Correct tax type and amount identified
        """
        # Arrange - SST receipt
        sst_text = "SST (6%): RM 9.00\nTotal: RM 159.00"

        with patch.object(ocr_service, 'extract_text') as mock_extract:
            mock_extract.return_value = MagicMock(raw_text=sst_text)

            # Act
            result = await ocr_service.extract_structured_data(Path("/tmp/test.jpg"))

            # Assert
            assert result.claim.sst_amount == 9.00
            assert result.claim.gst_amount is None

    @pytest.mark.asyncio
    @pytest.mark.malaysian
    async def test_extract_multilingual_receipt(self, ocr_service, malaysian_receipt_samples):
        """
        Test extraction from Malay language receipt

        Given: Receipt in Malay language
        When: extract_structured_data() is called
        Then: Data correctly extracted despite language difference
        """
        # Arrange
        malay_text = malaysian_receipt_samples["malay"]["text"]
        expected = malaysian_receipt_samples["malay"]["expected"]

        with patch.object(ocr_service, 'extract_text') as mock_extract:
            mock_extract.return_value = MagicMock(raw_text=malay_text)

            # Act
            result = await ocr_service.extract_structured_data(Path("/tmp/test.jpg"))

            # Assert
            assert result.claim.provider_name == expected["provider_name"]
            assert result.claim.member_id == expected["member_id"]

    @pytest.mark.asyncio
    @pytest.mark.confidence
    async def test_calculate_confidence_all_fields_present(self, ocr_service):
        """
        Test confidence calculation when all fields present

        Given: OCR result with all required fields detected
        When: calculate_confidence() is called
        Then: High overall confidence score returned
        """
        # Arrange
        from src.models.claim import ExtractedClaim

        claim = ExtractedClaim(
            member_id="M12345",
            member_name="John Doe",
            provider_name="Test Clinic",
            service_date=datetime(2024, 12, 15),
            receipt_number="RCP-001",
            total_amount=100.00,
        )

        ocr_result = MagicMock(
            field_confidences={
                "member_id": 0.98,
                "member_name": 0.95,
                "provider_name": 0.96,
                "service_date": 0.92,
                "receipt_number": 0.94,
                "total_amount": 0.93,
            }
        )

        # Act
        overall_score, field_scores = ocr_service.calculate_confidence(ocr_result, claim)

        # Assert
        assert overall_score >= 0.90  # Should be high confidence
        assert len(field_scores) == 6
        assert all(score >= 0.90 for score in field_scores.values())

    @pytest.mark.asyncio
    @pytest.mark.confidence
    async def test_calculate_confidence_missing_fields(self, ocr_service):
        """
        Test confidence calculation with missing optional fields

        Given: OCR result with only required fields
        When: calculate_confidence() is called
        Then: Confidence score still calculated correctly
        """
        # Arrange
        from src.models.claim import ExtractedClaim

        claim = ExtractedClaim(
            member_id="M12345",
            provider_name="Test Clinic",
            total_amount=100.00,
            # Missing: member_name, service_date, receipt_number
        )

        ocr_result = MagicMock(
            field_confidences={
                "member_id": 0.95,
                "provider_name": 0.92,
                "total_amount": 0.90,
            }
        )

        # Act
        overall_score, field_scores = ocr_service.calculate_confidence(ocr_result, claim)

        # Assert
        assert 0.75 <= overall_score < 0.90  # Should be medium confidence
        assert len(field_scores) == 3

    @pytest.mark.asyncio
    @pytest.mark.confidence
    async def test_calculate_confidence_low_ocr_scores(self, ocr_service):
        """
        Test confidence calculation with low OCR scores

        Given: OCR result with low individual field confidences
        When: calculate_confidence() is called
        Then: Low overall confidence score returned
        """
        # Arrange
        from src.models.claim import ExtractedClaim

        claim = ExtractedClaim(
            member_id="M12345",
            total_amount=100.00,
        )

        ocr_result = MagicMock(
            field_confidences={
                "member_id": 0.65,
                "total_amount": 0.70,
            }
        )

        # Act
        overall_score, field_scores = ocr_service.calculate_confidence(ocr_result, claim)

        # Assert
        assert overall_score < 0.75  # Should be low confidence

    @pytest.mark.asyncio
    async def test_extract_handles_ocr_errors(self, ocr_service):
        """
        Test error handling when OCR fails

        Given: Image that causes OCR engine to fail
        When: extract_text() is called
        Then: Appropriate error raised with context
        """
        # Arrange
        with patch.object(ocr_service.ocr, 'ocr', side_effect=Exception("OCR failed")):

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await ocr_service.extract_text(Path("/tmp/bad_image.jpg"))

            assert "OCR failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_handles_corrupt_image(self, ocr_service):
        """
        Test handling of corrupt/invalid image files

        Given: Corrupt image file
        When: extract_text() is called
        Then: Appropriate validation error raised
        """
        # Arrange
        corrupt_image = Path("/tmp/corrupt.jpg")

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await ocr_service.extract_text(corrupt_image)

        assert "image" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_extract_text_performance(self, ocr_service, test_data_dir):
        """
        Test OCR performance (should complete under 5 seconds)

        Given: Standard receipt image
        When: extract_text() is called
        Then: Completes in under 5 seconds
        """
        # Arrange
        test_image = test_data_dir / "sample_receipt.jpg"

        # Act
        import time
        start = time.time()
        result = await ocr_service.extract_text(test_image)
        duration = time.time() - start

        # Assert
        assert duration < 5.0  # Should be fast
        assert result is not None

    @pytest.mark.asyncio
    async def test_confidence_level_classification(self, ocr_service, confidence_test_cases):
        """
        Test confidence level classification (high/medium/low)

        Given: Various confidence scores
        When: Classified into levels
        Then: Correct level assigned per thresholds
        """
        for test_case in confidence_test_cases:
            # Act
            level = ocr_service._classify_confidence_level(test_case["confidence"])

            # Assert
            assert level == test_case["expected_level"], \
                f"Score {test_case['confidence']} should be {test_case['expected_level']}, got {level}"

    @pytest.mark.asyncio
    async def test_extract_creates_warnings_for_issues(self, ocr_service):
        """
        Test that extraction creates warnings for data quality issues

        Given: Receipt with ambiguous or unclear fields
        When: extract_structured_data() is called
        Then: Warnings list populated with issues
        """
        # Arrange - Receipt with unclear amount
        unclear_text = "Total: RM ???.00"

        with patch.object(ocr_service, 'extract_text') as mock_extract:
            mock_extract.return_value = MagicMock(raw_text=unclear_text)

            # Act
            result = await ocr_service.extract_structured_data(Path("/tmp/test.jpg"))

            # Assert
            assert len(result.warnings) > 0
            assert any("amount" in warning.lower() for warning in result.warnings)
