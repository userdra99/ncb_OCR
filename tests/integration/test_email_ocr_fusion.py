"""
Integration tests for complete email → OCR → fusion pipeline.

Tests real-world scenarios with sample data, multi-language fusion,
and confidence level routing.
"""

import pytest
from datetime import date
from decimal import Decimal
from typing import Dict, Any

from src.services.email_parser import EmailParser
from src.services.ocr_service import OCRService
from src.services.data_fusion import DataFusionEngine, FusionConfig
from src.models.extraction import (
    EmailExtractionResult,
    OCRExtractionResult,
    FusedExtractionResult,
    ConfidenceLevel
)


@pytest.fixture
def email_parser():
    """Create email parser instance."""
    return EmailParser()


@pytest.fixture
def ocr_service():
    """Create OCR service instance (mocked for tests)."""
    return OCRService(use_gpu=False)


@pytest.fixture
def fusion_engine():
    """Create fusion engine instance."""
    return DataFusionEngine(FusionConfig())


class TestEmailOCRFusionPipeline:
    """Test complete email → OCR → fusion pipeline."""

    @pytest.mark.asyncio
    async def test_perfect_extraction_pipeline(self, email_parser, ocr_service, fusion_engine):
        """Test pipeline with perfect extraction from both sources."""
        # Sample email content
        email_content = """
        Dear TPA,

        Please process claim for:
        Member ID: M12345
        Member Name: Ahmad bin Abdullah
        Service Date: 15/01/2024

        Receipt attached.
        """

        # Sample OCR result (simulated)
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            member_name="Ahmad bin Abdullah",
            provider_name="Klinik Dr. Lee",
            service_date=date(2024, 1, 15),
            receipt_number="RCP-001",
            total_amount=Decimal("155.50"),
            gst_sst_amount=Decimal("9.33"),
            field_confidences={
                "member_id": 0.95,
                "member_name": 0.92,
                "provider_name": 0.90,
                "service_date": 0.93,
                "receipt_number": 0.88,
                "total_amount": 0.96,
                "gst_sst_amount": 0.85
            }
        )

        # Parse email
        email_result = await email_parser.parse_email(email_content)

        # Fuse results
        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        # Verify fusion
        assert fused.member_id == "M12345"
        assert fused.confidence_level == ConfidenceLevel.HIGH
        assert fused.overall_confidence >= 0.90
        assert len(fused.conflicts) == 0
        assert fused.email_extraction_available is True
        assert fused.ocr_extraction_available is True

    @pytest.mark.asyncio
    async def test_email_only_extraction(self, email_parser, fusion_engine):
        """Test pipeline when only email extraction available."""
        email_content = """
        Claim Details:
        Member ID: M12345
        Member Name: Lee Mei Ling
        Service Date: 20/01/2024
        Total Amount: RM 200.00
        """

        email_result = await email_parser.parse_email(email_content)
        fused = await fusion_engine.fuse_extractions(email_result, None)

        assert fused.member_id == "M12345"
        assert fused.total_amount == Decimal("200.00")
        assert fused.email_extraction_available is True
        assert fused.ocr_extraction_available is False
        assert all(source == "email" for source in fused.data_sources.values())

    @pytest.mark.asyncio
    async def test_ocr_only_extraction(self, fusion_engine):
        """Test pipeline when only OCR extraction available."""
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            provider_name="Hospital Pantai",
            total_amount=Decimal("350.00"),
            service_date=date(2024, 1, 25),
            field_confidences={
                "member_id": 0.88,
                "provider_name": 0.92,
                "total_amount": 0.94,
                "service_date": 0.90
            }
        )

        fused = await fusion_engine.fuse_extractions(None, ocr_result)

        assert fused.member_id == "M12345"
        assert fused.total_amount == Decimal("350.00")
        assert fused.email_extraction_available is False
        assert fused.ocr_extraction_available is True
        assert all(source == "ocr" for source in fused.data_sources.values())

    @pytest.mark.asyncio
    async def test_conflicting_amounts_resolved(self, email_parser, fusion_engine):
        """Test conflict resolution when email and OCR disagree on amount."""
        email_content = """
        Member: M12345
        Amount: RM 150.00
        Date: 10/01/2024
        """

        ocr_result = OCRExtractionResult(
            member_id="M12345",
            total_amount=Decimal("155.50"),  # Different from email
            service_date=date(2024, 1, 10),
            field_confidences={
                "member_id": 0.90,
                "total_amount": 0.95,
                "service_date": 0.88
            }
        )

        email_result = await email_parser.parse_email(email_content)
        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        # Should prefer OCR for amounts
        assert fused.total_amount == Decimal("155.50")
        assert len(fused.conflicts) >= 1

        # Find amount conflict
        amount_conflict = next(
            (c for c in fused.conflicts if c.field_name == "total_amount"),
            None
        )
        assert amount_conflict is not None
        assert amount_conflict.chosen_source == "ocr"

    @pytest.mark.asyncio
    async def test_high_confidence_routing(self, email_parser, fusion_engine):
        """Test HIGH confidence level routing (>= 90%)."""
        email_content = """
        Member ID: M12345
        Member Name: Kumar Rajan
        Service Date: 15/01/2024
        """

        ocr_result = OCRExtractionResult(
            member_id="M12345",
            member_name="Kumar Rajan",
            provider_name="Klinik Kesihatan",
            service_date=date(2024, 1, 15),
            total_amount=Decimal("100.00"),
            field_confidences={
                "member_id": 0.95,
                "member_name": 0.93,
                "provider_name": 0.92,
                "service_date": 0.94,
                "total_amount": 0.96
            }
        )

        email_result = await email_parser.parse_email(email_content)
        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.confidence_level == ConfidenceLevel.HIGH
        assert fused.overall_confidence >= 0.90
        # Should auto-submit to NCB

    @pytest.mark.asyncio
    async def test_medium_confidence_routing(self, email_parser, fusion_engine):
        """Test MEDIUM confidence level routing (75-89%)."""
        email_content = """
        Member: M12345
        Amount: RM 100.00
        """

        ocr_result = OCRExtractionResult(
            member_id="M12346",  # Slight conflict
            total_amount=Decimal("105.00"),  # Slight conflict
            service_date=date(2024, 1, 15),
            field_confidences={
                "member_id": 0.80,
                "total_amount": 0.82,
                "service_date": 0.78
            }
        )

        email_result = await email_parser.parse_email(email_content)
        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.confidence_level == ConfidenceLevel.MEDIUM
        assert 0.75 <= fused.overall_confidence < 0.90
        # Should submit with review flag

    @pytest.mark.asyncio
    async def test_low_confidence_routing(self, email_parser, fusion_engine):
        """Test LOW confidence level routing (< 75%)."""
        email_content = """
        Member: M12345
        Amount: RM 100.00
        """

        ocr_result = OCRExtractionResult(
            member_id="M99999",  # Major conflict
            total_amount=Decimal("500.00"),  # Major conflict
            service_date=date(2024, 2, 1),  # Major conflict
            field_confidences={
                "member_id": 0.65,
                "total_amount": 0.70,
                "service_date": 0.68
            }
        )

        email_result = await email_parser.parse_email(email_content)
        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.confidence_level == ConfidenceLevel.LOW
        assert fused.overall_confidence < 0.75
        # Should route to exception queue


class TestMultiLanguageFusion:
    """Test fusion with multi-language content."""

    @pytest.mark.asyncio
    async def test_malay_language_fusion(self, email_parser, fusion_engine):
        """Test fusion with Malay content."""
        email_content = """
        ID Ahli: M12345
        Nama: Ahmad bin Abdullah
        Tarikh Perkhidmatan: 15/01/2024
        Jumlah: RM 150.00
        """

        ocr_result = OCRExtractionResult(
            member_id="M12345",
            member_name="Ahmad bin Abdullah",
            service_date=date(2024, 1, 15),
            total_amount=Decimal("150.00"),
            provider_name="Klinik Kesihatan",
            field_confidences={
                "member_id": 0.90,
                "member_name": 0.88,
                "service_date": 0.92,
                "total_amount": 0.94,
                "provider_name": 0.87
            }
        )

        email_result = await email_parser.parse_email(email_content)
        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.member_id == "M12345"
        assert fused.confidence_level in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]

    @pytest.mark.asyncio
    async def test_chinese_language_fusion(self, fusion_engine):
        """Test fusion with Chinese content from OCR."""
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            member_name="李明",  # Chinese name
            provider_name="李医生诊所",  # Chinese clinic name
            service_date=date(2024, 1, 15),
            total_amount=Decimal("120.00"),
            field_confidences={
                "member_id": 0.92,
                "member_name": 0.85,
                "provider_name": 0.83,
                "service_date": 0.90,
                "total_amount": 0.94
            }
        )

        fused = await fusion_engine.fuse_extractions(None, ocr_result)

        assert fused.member_name == "李明"
        assert fused.provider_name == "李医生诊所"
        assert fused.confidence_level in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]

    @pytest.mark.asyncio
    async def test_tamil_language_fusion(self, fusion_engine):
        """Test fusion with Tamil content from OCR."""
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            member_name="குமார்",  # Tamil name
            provider_name="குமார் மருத்துவமனை",  # Tamil clinic name
            service_date=date(2024, 1, 15),
            total_amount=Decimal("180.00"),
            field_confidences={
                "member_id": 0.90,
                "member_name": 0.82,
                "provider_name": 0.80,
                "service_date": 0.88,
                "total_amount": 0.92
            }
        )

        fused = await fusion_engine.fuse_extractions(None, ocr_result)

        assert fused.member_name == "குமார்"
        assert fused.provider_name == "குமார் மருத்துவமனை"
        assert fused.confidence_level in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]


class TestRealWorldScenarios:
    """Test real-world claim scenarios."""

    @pytest.mark.asyncio
    async def test_clinic_visit_claim(self, fusion_engine):
        """Test typical clinic visit claim."""
        email_result = EmailExtractionResult(
            member_id="M12345",
            member_name="Sarah binti Ismail",
            service_date=date(2024, 1, 20),
            field_confidences={
                "member_id": 0.85,
                "member_name": 0.80,
                "service_date": 0.82
            }
        )

        ocr_result = OCRExtractionResult(
            member_id="M12345",
            member_name="Sarah binti Ismail",
            provider_name="Klinik Dr. Wong",
            provider_address="123 Jalan Utama, 50000 KL",
            service_date=date(2024, 1, 20),
            receipt_number="INV-2024-001",
            total_amount=Decimal("85.00"),
            gst_sst_amount=Decimal("5.10"),
            field_confidences={
                "member_id": 0.95,
                "member_name": 0.92,
                "provider_name": 0.90,
                "provider_address": 0.88,
                "service_date": 0.93,
                "receipt_number": 0.87,
                "total_amount": 0.96,
                "gst_sst_amount": 0.84
            }
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.member_id == "M12345"
        assert fused.total_amount == Decimal("85.00")
        assert fused.provider_name == "Klinik Dr. Wong"
        assert fused.confidence_level == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_hospital_claim(self, fusion_engine):
        """Test hospital claim with itemized charges."""
        ocr_result = OCRExtractionResult(
            member_id="M67890",
            member_name="Tan Ai Ling",
            provider_name="Hospital Pantai Kuala Lumpur",
            provider_address="8 Jalan Bukit Pantai, 59100 KL",
            service_date=date(2024, 1, 18),
            receipt_number="HPT-2024-5678",
            total_amount=Decimal("1250.00"),
            gst_sst_amount=Decimal("75.00"),
            itemized_charges=[
                {"description": "Consultation", "amount": Decimal("200.00")},
                {"description": "X-Ray", "amount": Decimal("350.00")},
                {"description": "Lab Tests", "amount": Decimal("500.00")},
                {"description": "Medication", "amount": Decimal("200.00")}
            ],
            field_confidences={
                "member_id": 0.94,
                "member_name": 0.91,
                "provider_name": 0.93,
                "provider_address": 0.89,
                "service_date": 0.92,
                "receipt_number": 0.90,
                "total_amount": 0.96,
                "gst_sst_amount": 0.88
            }
        )

        fused = await fusion_engine.fuse_extractions(None, ocr_result)

        assert fused.total_amount == Decimal("1250.00")
        assert len(fused.itemized_charges) == 4
        assert fused.confidence_level == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_pharmacy_claim(self, fusion_engine):
        """Test pharmacy claim."""
        email_result = EmailExtractionResult(
            member_id="M11111",
            member_name="Kumar s/o Rajan",
            service_date=date(2024, 1, 22),
            field_confidences={
                "member_id": 0.88,
                "member_name": 0.85,
                "service_date": 0.83
            }
        )

        ocr_result = OCRExtractionResult(
            member_id="M11111",
            member_name="Kumar s/o Rajan",
            provider_name="Farmasi Caring",
            service_date=date(2024, 1, 22),
            receipt_number="PHR-001234",
            total_amount=Decimal("45.50"),
            field_confidences={
                "member_id": 0.92,
                "member_name": 0.90,
                "provider_name": 0.88,
                "service_date": 0.91,
                "receipt_number": 0.86,
                "total_amount": 0.94
            }
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.member_id == "M11111"
        assert fused.total_amount == Decimal("45.50")
        assert fused.provider_name == "Farmasi Caring"
        assert fused.confidence_level == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_dental_claim(self, fusion_engine):
        """Test dental claim."""
        ocr_result = OCRExtractionResult(
            member_id="M22222",
            member_name="David Lim",
            provider_name="Dental Care Centre",
            provider_address="45 Jalan Dentist, 50000 KL",
            service_date=date(2024, 1, 25),
            receipt_number="DEN-2024-789",
            total_amount=Decimal("320.00"),
            gst_sst_amount=Decimal("19.20"),
            itemized_charges=[
                {"description": "Scaling & Polishing", "amount": Decimal("120.00")},
                {"description": "Filling (1 tooth)", "amount": Decimal("200.00")}
            ],
            field_confidences={
                "member_id": 0.93,
                "member_name": 0.90,
                "provider_name": 0.91,
                "provider_address": 0.87,
                "service_date": 0.92,
                "receipt_number": 0.88,
                "total_amount": 0.95,
                "gst_sst_amount": 0.86
            }
        )

        fused = await fusion_engine.fuse_extractions(None, ocr_result)

        assert fused.total_amount == Decimal("320.00")
        assert len(fused.itemized_charges) == 2
        assert fused.confidence_level == ConfidenceLevel.HIGH


class TestEdgeCasesIntegration:
    """Test edge cases in integration pipeline."""

    @pytest.mark.asyncio
    async def test_missing_receipt_attachment(self, email_parser, fusion_engine):
        """Test when email mentions attachment but OCR unavailable."""
        email_content = """
        Member ID: M12345
        Please see attached receipt.
        """

        email_result = await email_parser.parse_email(email_content)
        fused = await fusion_engine.fuse_extractions(email_result, None)

        assert fused.member_id == "M12345"
        assert fused.ocr_extraction_available is False
        assert fused.confidence_level == ConfidenceLevel.LOW  # Missing data

    @pytest.mark.asyncio
    async def test_corrupted_receipt_image(self, email_parser, fusion_engine):
        """Test when OCR extraction fails due to corrupted image."""
        email_content = """
        Member ID: M12345
        Amount: RM 100.00
        """

        # OCR failed, returning minimal data
        ocr_result = OCRExtractionResult(
            member_id=None,
            total_amount=None,
            field_confidences={}
        )

        email_result = await email_parser.parse_email(email_content)
        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        # Should fall back to email data
        assert fused.member_id == "M12345"
        assert fused.total_amount == Decimal("100.00")
        assert all(source == "email" for source in fused.data_sources.values())

    @pytest.mark.asyncio
    async def test_handwritten_receipt(self, fusion_engine):
        """Test OCR with handwritten receipt (lower confidence)."""
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            provider_name="Klinik Ahmad",
            total_amount=Decimal("75.00"),
            service_date=date(2024, 1, 20),
            field_confidences={
                "member_id": 0.72,  # Lower due to handwriting
                "provider_name": 0.68,
                "total_amount": 0.75,
                "service_date": 0.70
            }
        )

        fused = await fusion_engine.fuse_extractions(None, ocr_result)

        assert fused.confidence_level == ConfidenceLevel.MEDIUM
        # Should flag for manual review
