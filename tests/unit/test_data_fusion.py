"""
Unit tests for DataFusionEngine.

Tests field merging, confidence boosting, conflict resolution,
and validation integration.
"""

import pytest
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from src.services.data_fusion import (
    DataFusionEngine,
    FusionConfig,
    FusionStrategy,
    FieldConflict,
    ConflictResolution
)
from src.models.extraction import (
    EmailExtractionResult,
    OCRExtractionResult,
    FusedExtractionResult,
    ConfidenceLevel
)


class TestDataFusionEngine:
    """Test data fusion engine."""

    @pytest.fixture
    def fusion_engine(self):
        """Create fusion engine with default config."""
        return DataFusionEngine(FusionConfig())

    @pytest.fixture
    def custom_fusion_engine(self):
        """Create fusion engine with custom config."""
        config = FusionConfig(
            exact_match_boost=0.15,
            fuzzy_match_boost=0.08,
            min_confidence_threshold=0.70
        )
        return DataFusionEngine(config)

    # ==================== Field Merging Tests ====================

    @pytest.mark.asyncio
    async def test_exact_match_boosts_confidence(self, fusion_engine):
        """When email and OCR agree exactly, confidence gets +10% boost."""
        email_result = EmailExtractionResult(
            member_id="M12345",
            field_confidences={"member_id": 0.85}
        )
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            field_confidences={"member_id": 0.80}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        # Should use email (preference) with boosted confidence
        assert fused.member_id == "M12345"
        assert fused.field_confidences["member_id"] >= 0.90  # 0.85 + 0.10 boost
        assert fused.data_sources["member_id"] == "both"  # Agreement
        assert len(fused.conflicts) == 0

    @pytest.mark.asyncio
    async def test_fuzzy_match_boosts_confidence(self, fusion_engine):
        """Similar values get smaller +5% boost."""
        email_result = EmailExtractionResult(
            provider_name="Klinik Dr. Ahmad",
            field_confidences={"provider_name": 0.80}
        )
        ocr_result = OCRExtractionResult(
            provider_name="Klinik Dr Ahmad",  # Missing period
            field_confidences={"provider_name": 0.85}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        # Should detect fuzzy match and boost confidence
        assert fused.provider_name == "Klinik Dr. Ahmad"  # Email preference
        assert 0.84 <= fused.field_confidences["provider_name"] <= 0.86  # ~0.80 + 0.05
        assert fused.data_sources["provider_name"] == "both"

    @pytest.mark.asyncio
    async def test_prefer_ocr_for_amounts(self, fusion_engine):
        """For total_amount, prefer OCR when available."""
        email_result = EmailExtractionResult(
            total_amount=Decimal("150.00"),
            field_confidences={"total_amount": 0.80}
        )
        ocr_result = OCRExtractionResult(
            total_amount=Decimal("155.50"),
            field_confidences={"total_amount": 0.90}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.total_amount == Decimal("155.50")  # OCR value
        assert fused.field_confidences["total_amount"] == 0.90
        assert fused.data_sources["total_amount"] == "ocr"

        # Should record conflict
        assert len(fused.conflicts) == 1
        assert fused.conflicts[0].field_name == "total_amount"
        assert fused.conflicts[0].email_value == "150.00"
        assert fused.conflicts[0].ocr_value == "155.50"
        assert fused.conflicts[0].resolution == ConflictResolution.USED_OCR

    @pytest.mark.asyncio
    async def test_prefer_email_for_member_id(self, fusion_engine):
        """For member_id, prefer email when available."""
        email_result = EmailExtractionResult(
            member_id="M12345",
            field_confidences={"member_id": 0.85}
        )
        ocr_result = OCRExtractionResult(
            member_id="M12345X",  # OCR error
            field_confidences={"member_id": 0.75}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.member_id == "M12345"  # Email value
        assert fused.field_confidences["member_id"] == 0.85
        assert fused.data_sources["member_id"] == "email"

        # Should record conflict
        assert len(fused.conflicts) == 1
        assert fused.conflicts[0].field_name == "member_id"
        assert fused.conflicts[0].resolution == ConflictResolution.USED_EMAIL

    @pytest.mark.asyncio
    async def test_use_higher_confidence_when_conflict(self, fusion_engine):
        """When no preference rule, use higher confidence value."""
        email_result = EmailExtractionResult(
            receipt_number="RCP-001",
            field_confidences={"receipt_number": 0.70}
        )
        ocr_result = OCRExtractionResult(
            receipt_number="RCP-002",
            field_confidences={"receipt_number": 0.85}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.receipt_number == "RCP-002"  # Higher confidence
        assert fused.field_confidences["receipt_number"] == 0.85
        assert fused.data_sources["receipt_number"] == "ocr"

        assert len(fused.conflicts) == 1
        assert fused.conflicts[0].resolution == ConflictResolution.USED_HIGHER_CONFIDENCE

    @pytest.mark.asyncio
    async def test_one_source_missing_field(self, fusion_engine):
        """When only one source has a field, use it."""
        email_result = EmailExtractionResult(
            member_id="M12345",
            provider_name=None,  # Missing
            field_confidences={"member_id": 0.85}
        )
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            provider_name="Klinik Ahmad",
            field_confidences={
                "member_id": 0.80,
                "provider_name": 0.90
            }
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.provider_name == "Klinik Ahmad"
        assert fused.field_confidences["provider_name"] == 0.90
        assert fused.data_sources["provider_name"] == "ocr"
        assert len(fused.conflicts) == 0  # No conflict, just missing

    @pytest.mark.asyncio
    async def test_both_sources_missing_field(self, fusion_engine):
        """When both sources missing, field remains None."""
        email_result = EmailExtractionResult(
            member_id="M12345",
            provider_address=None,
            field_confidences={"member_id": 0.85}
        )
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            provider_address=None,
            field_confidences={"member_id": 0.80}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.provider_address is None
        assert "provider_address" not in fused.field_confidences
        assert "provider_address" not in fused.data_sources

    @pytest.mark.asyncio
    async def test_only_email_available(self, fusion_engine):
        """When only email extraction available, use it."""
        email_result = EmailExtractionResult(
            member_id="M12345",
            total_amount=Decimal("100.00"),
            field_confidences={
                "member_id": 0.85,
                "total_amount": 0.80
            }
        )

        fused = await fusion_engine.fuse_extractions(email_result, None)

        assert fused.member_id == "M12345"
        assert fused.total_amount == Decimal("100.00")
        assert fused.email_extraction_available is True
        assert fused.ocr_extraction_available is False
        assert all(source == "email" for source in fused.data_sources.values())
        assert len(fused.conflicts) == 0

    @pytest.mark.asyncio
    async def test_only_ocr_available(self, fusion_engine):
        """When only OCR extraction available, use it."""
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            total_amount=Decimal("100.00"),
            field_confidences={
                "member_id": 0.80,
                "total_amount": 0.90
            }
        )

        fused = await fusion_engine.fuse_extractions(None, ocr_result)

        assert fused.member_id == "M12345"
        assert fused.total_amount == Decimal("100.00")
        assert fused.email_extraction_available is False
        assert fused.ocr_extraction_available is True
        assert all(source == "ocr" for source in fused.data_sources.values())
        assert len(fused.conflicts) == 0

    @pytest.mark.asyncio
    async def test_neither_source_available(self, fusion_engine):
        """When neither source available, raise error."""
        with pytest.raises(ValueError, match="At least one extraction result required"):
            await fusion_engine.fuse_extractions(None, None)

    # ==================== Confidence Boosting Tests ====================

    @pytest.mark.asyncio
    async def test_exact_match_boost_amount(self, fusion_engine):
        """Test exact match boost for amount fields."""
        email_result = EmailExtractionResult(
            total_amount=Decimal("155.50"),
            field_confidences={"total_amount": 0.75}
        )
        ocr_result = OCRExtractionResult(
            total_amount=Decimal("155.50"),
            field_confidences={"total_amount": 0.80}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        # OCR preference for amounts, but with boost
        assert fused.total_amount == Decimal("155.50")
        assert fused.field_confidences["total_amount"] >= 0.90  # 0.80 + 0.10
        assert fused.data_sources["total_amount"] == "both"

    @pytest.mark.asyncio
    async def test_custom_boost_values(self, custom_fusion_engine):
        """Test custom boost values in config."""
        email_result = EmailExtractionResult(
            member_id="M12345",
            field_confidences={"member_id": 0.70}
        )
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            field_confidences={"member_id": 0.75}
        )

        fused = await custom_fusion_engine.fuse_extractions(email_result, ocr_result)

        # Should use custom exact_match_boost=0.15
        assert fused.field_confidences["member_id"] >= 0.85  # 0.70 + 0.15

    @pytest.mark.asyncio
    async def test_confidence_capped_at_100(self, fusion_engine):
        """Confidence should never exceed 1.0."""
        email_result = EmailExtractionResult(
            member_id="M12345",
            field_confidences={"member_id": 0.95}
        )
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            field_confidences={"member_id": 0.98}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.field_confidences["member_id"] <= 1.0
        assert fused.field_confidences["member_id"] == 1.0  # Should be capped

    @pytest.mark.asyncio
    async def test_no_boost_on_conflict(self, fusion_engine):
        """No confidence boost when values conflict."""
        email_result = EmailExtractionResult(
            total_amount=Decimal("100.00"),
            field_confidences={"total_amount": 0.80}
        )
        ocr_result = OCRExtractionResult(
            total_amount=Decimal("150.00"),
            field_confidences={"total_amount": 0.85}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        # Should use OCR value without boost (conflict)
        assert fused.total_amount == Decimal("150.00")
        assert fused.field_confidences["total_amount"] == 0.85  # No boost
        assert len(fused.conflicts) == 1

    # ==================== Conflict Resolution Tests ====================

    @pytest.mark.asyncio
    async def test_conflict_details_captured(self, fusion_engine):
        """Conflict details should be fully captured."""
        email_result = EmailExtractionResult(
            service_date=date(2024, 1, 15),
            field_confidences={"service_date": 0.80}
        )
        ocr_result = OCRExtractionResult(
            service_date=date(2024, 1, 16),
            field_confidences={"service_date": 0.85}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert len(fused.conflicts) == 1
        conflict = fused.conflicts[0]
        assert conflict.field_name == "service_date"
        assert conflict.email_value == "2024-01-15"
        assert conflict.ocr_value == "2024-01-16"
        assert conflict.email_confidence == 0.80
        assert conflict.ocr_confidence == 0.85
        assert conflict.chosen_value == "2024-01-16"
        assert conflict.chosen_source == "ocr"
        assert conflict.resolution == ConflictResolution.USED_HIGHER_CONFIDENCE

    @pytest.mark.asyncio
    async def test_multiple_conflicts(self, fusion_engine):
        """Handle multiple field conflicts."""
        email_result = EmailExtractionResult(
            total_amount=Decimal("100.00"),
            service_date=date(2024, 1, 15),
            receipt_number="RCP-001",
            field_confidences={
                "total_amount": 0.75,
                "service_date": 0.80,
                "receipt_number": 0.85
            }
        )
        ocr_result = OCRExtractionResult(
            total_amount=Decimal("110.00"),
            service_date=date(2024, 1, 16),
            receipt_number="RCP-002",
            field_confidences={
                "total_amount": 0.90,
                "service_date": 0.85,
                "receipt_number": 0.80
            }
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert len(fused.conflicts) == 3
        conflict_fields = {c.field_name for c in fused.conflicts}
        assert conflict_fields == {"total_amount", "service_date", "receipt_number"}

    @pytest.mark.asyncio
    async def test_date_exact_match(self, fusion_engine):
        """Dates should match exactly for boost."""
        email_result = EmailExtractionResult(
            service_date=date(2024, 1, 15),
            field_confidences={"service_date": 0.80}
        )
        ocr_result = OCRExtractionResult(
            service_date=date(2024, 1, 15),
            field_confidences={"service_date": 0.85}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.service_date == date(2024, 1, 15)
        assert fused.field_confidences["service_date"] >= 0.90  # Boost applied
        assert fused.data_sources["service_date"] == "both"
        assert len(fused.conflicts) == 0

    # ==================== Validation Integration Tests ====================

    @pytest.mark.asyncio
    async def test_validation_failures_recorded(self, fusion_engine):
        """Validation failures should be recorded in result."""
        email_result = EmailExtractionResult(
            member_id="INVALID",  # Invalid format
            total_amount=Decimal("-50.00"),  # Negative
            field_confidences={
                "member_id": 0.80,
                "total_amount": 0.85
            }
        )
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            total_amount=Decimal("100.00"),
            field_confidences={
                "member_id": 0.85,
                "total_amount": 0.90
            }
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        # Should use OCR values (valid)
        assert fused.member_id == "M12345"
        assert fused.total_amount == Decimal("100.00")

        # Validation failures should be recorded
        assert len(fused.validation_failures) > 0
        validation_fields = {vf["field"] for vf in fused.validation_failures}
        assert "member_id" in validation_fields or "total_amount" in validation_fields

    @pytest.mark.asyncio
    async def test_overall_confidence_calculation(self, fusion_engine):
        """Overall confidence should be weighted average."""
        email_result = EmailExtractionResult(
            member_id="M12345",
            total_amount=Decimal("100.00"),
            service_date=date(2024, 1, 15),
            field_confidences={
                "member_id": 0.90,
                "total_amount": 0.85,
                "service_date": 0.80
            }
        )
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            total_amount=Decimal("100.00"),
            service_date=date(2024, 1, 15),
            field_confidences={
                "member_id": 0.88,
                "total_amount": 0.92,
                "service_date": 0.85
            }
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        # All exact matches, should have high overall confidence
        assert fused.overall_confidence >= 0.90
        assert fused.confidence_level == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_confidence_level_high(self, fusion_engine):
        """Overall confidence >= 0.90 should be HIGH."""
        email_result = EmailExtractionResult(
            member_id="M12345",
            field_confidences={"member_id": 0.92}
        )
        ocr_result = OCRExtractionResult(
            member_id="M12345",
            field_confidences={"member_id": 0.95}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.overall_confidence >= 0.90
        assert fused.confidence_level == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_confidence_level_medium(self, fusion_engine):
        """Overall confidence 0.75-0.89 should be MEDIUM."""
        email_result = EmailExtractionResult(
            member_id="M12345",
            total_amount=Decimal("100.00"),
            field_confidences={
                "member_id": 0.80,
                "total_amount": 0.85
            }
        )
        ocr_result = OCRExtractionResult(
            member_id="M12346",  # Conflict
            total_amount=Decimal("110.00"),  # Conflict
            field_confidences={
                "member_id": 0.75,
                "total_amount": 0.80
            }
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert 0.75 <= fused.overall_confidence < 0.90
        assert fused.confidence_level == ConfidenceLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_confidence_level_low(self, fusion_engine):
        """Overall confidence < 0.75 should be LOW."""
        email_result = EmailExtractionResult(
            member_id="M12345",
            total_amount=Decimal("100.00"),
            field_confidences={
                "member_id": 0.65,
                "total_amount": 0.70
            }
        )
        ocr_result = OCRExtractionResult(
            member_id="M12346",  # Conflict
            total_amount=Decimal("110.00"),  # Conflict
            field_confidences={
                "member_id": 0.68,
                "total_amount": 0.72
            }
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.overall_confidence < 0.75
        assert fused.confidence_level == ConfidenceLevel.LOW

    # ==================== Edge Cases ====================

    @pytest.mark.asyncio
    async def test_empty_string_vs_none(self, fusion_engine):
        """Empty strings and None should be treated differently."""
        email_result = EmailExtractionResult(
            provider_address="",  # Empty string
            field_confidences={"provider_address": 0.80}
        )
        ocr_result = OCRExtractionResult(
            provider_address=None,  # None
            field_confidences={}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        # Empty string from email should be used
        assert fused.provider_address == ""
        assert fused.data_sources["provider_address"] == "email"

    @pytest.mark.asyncio
    async def test_zero_amount(self, fusion_engine):
        """Zero amounts should be valid."""
        email_result = EmailExtractionResult(
            total_amount=Decimal("0.00"),
            field_confidences={"total_amount": 0.85}
        )
        ocr_result = OCRExtractionResult(
            total_amount=Decimal("0.00"),
            field_confidences={"total_amount": 0.90}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        assert fused.total_amount == Decimal("0.00")
        assert fused.data_sources["total_amount"] == "both"  # Exact match

    @pytest.mark.asyncio
    async def test_very_similar_amounts(self, fusion_engine):
        """Very similar amounts (rounding) should fuzzy match."""
        email_result = EmailExtractionResult(
            total_amount=Decimal("155.50"),
            field_confidences={"total_amount": 0.80}
        )
        ocr_result = OCRExtractionResult(
            total_amount=Decimal("155.49"),  # 1 cent difference
            field_confidences={"total_amount": 0.85}
        )

        fused = await fusion_engine.fuse_extractions(email_result, ocr_result)

        # Should still be treated as conflict (not fuzzy match for amounts)
        assert len(fused.conflicts) == 1
        assert fused.conflicts[0].field_name == "total_amount"


class TestFusionStrategies:
    """Test individual fusion strategies."""

    @pytest.mark.asyncio
    async def test_ocr_preference_strategy(self):
        """Test OCR preference strategy."""
        config = FusionConfig()
        strategy = config.get_strategy("total_amount")

        assert strategy == FusionStrategy.PREFER_OCR

    @pytest.mark.asyncio
    async def test_email_preference_strategy(self):
        """Test email preference strategy."""
        config = FusionConfig()
        strategy = config.get_strategy("member_id")

        assert strategy == FusionStrategy.PREFER_EMAIL

    @pytest.mark.asyncio
    async def test_higher_confidence_strategy(self):
        """Test higher confidence strategy (default)."""
        config = FusionConfig()
        strategy = config.get_strategy("receipt_number")

        assert strategy == FusionStrategy.USE_HIGHER_CONFIDENCE

    @pytest.mark.asyncio
    async def test_custom_strategy_mapping(self):
        """Test custom strategy mapping in config."""
        config = FusionConfig(
            field_strategies={
                "custom_field": FusionStrategy.PREFER_OCR
            }
        )

        assert config.get_strategy("custom_field") == FusionStrategy.PREFER_OCR
        assert config.get_strategy("other_field") == FusionStrategy.USE_HIGHER_CONFIDENCE
