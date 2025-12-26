"""Data fusion engine for merging email and OCR extractions."""

from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
from pydantic import BaseModel, Field
from difflib import SequenceMatcher

from src.models.extraction import EmailExtractionResult, ExtractionResult
from src.utils.logging import get_logger

logger = get_logger(__name__)


class FusionConfig(BaseModel):
    """Configuration for data fusion engine."""

    # Confidence boost amounts
    exact_match_boost: float = 0.10
    fuzzy_match_boost: float = 0.05

    # Field preference rules
    prefer_ocr_fields: List[str] = Field(
        default_factory=lambda: [
            "provider_name",
            "total_amount",
            "service_date",
            "receipt_number",
            "gst_sst_amount",
            "provider_address",
        ]
    )
    prefer_email_fields: List[str] = Field(
        default_factory=lambda: ["member_id", "member_name", "policy_number"]
    )

    # Fuzzy matching threshold
    fuzzy_match_threshold: float = 0.85

    # Maximum confidence (cap)
    max_confidence: float = 0.98

    # Confidence level thresholds
    high_confidence_threshold: float = 0.90
    medium_confidence_threshold: float = 0.75


class FieldConflict(BaseModel):
    """Represents a conflict between email and OCR extraction."""

    field_name: str
    email_value: Optional[str]
    email_confidence: float
    ocr_value: Optional[str]
    ocr_confidence: float
    resolution: str  # 'used_email', 'used_ocr', 'used_higher_confidence'
    reason: str


class FusedExtractionResult(BaseModel):
    """Result of fusing email and OCR extractions."""

    # All claim fields
    member_id: Optional[str] = None
    member_name: Optional[str] = None
    provider_name: Optional[str] = None
    service_date: Optional[datetime] = None
    receipt_number: Optional[str] = None
    total_amount: Optional[float] = None
    gst_sst_amount: Optional[float] = None
    provider_address: Optional[str] = None
    policy_number: Optional[str] = None

    # Fusion metadata
    field_confidences: Dict[str, float] = Field(default_factory=dict)
    data_sources: Dict[str, str] = Field(
        default_factory=dict
    )  # 'email', 'ocr', 'both'
    confidence_boosts: Dict[str, float] = Field(default_factory=dict)
    conflicts: List[FieldConflict] = Field(default_factory=list)

    # Overall metrics
    overall_confidence: float = 0.0
    confidence_level: str = "low"  # 'high', 'medium', 'low'
    warnings: List[str] = Field(default_factory=list)

    # Audit trail
    fusion_timestamp: datetime = Field(default_factory=datetime.now)
    email_extraction_available: bool = False
    ocr_extraction_available: bool = False

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "member_id": "M12345",
                "member_name": "John Tan",
                "provider_name": "Klinik Kesihatan",
                "total_amount": 150.00,
                "field_confidences": {
                    "member_id": 0.95,
                    "provider_name": 0.92,
                    "total_amount": 0.95,
                },
                "data_sources": {
                    "member_id": "email",
                    "provider_name": "both",
                    "total_amount": "ocr",
                },
                "overall_confidence": 0.94,
                "confidence_level": "high",
            }
        }


class DataFusionEngine:
    """
    Merges email and OCR extractions with intelligent conflict resolution.

    Strategy:
    1. Prefer OCR for receipt-specific fields
    2. Prefer email for member-specific fields
    3. Boost confidence when sources agree
    4. Log and resolve conflicts
    """

    def __init__(self, config: Optional[FusionConfig] = None):
        """Initialize fusion engine with configuration."""
        self.config = config or FusionConfig()
        self.logger = get_logger(__name__)

    async def fuse_extractions(
        self,
        email_extraction: Optional[EmailExtractionResult],
        ocr_extraction: Optional[ExtractionResult],
    ) -> FusedExtractionResult:
        """
        Fuse email and OCR extractions.

        Args:
            email_extraction: Result from email parsing (Phase 1)
            ocr_extraction: Result from OCR service (existing)

        Returns:
            FusedExtractionResult with merged data
        """
        self.logger.info(
            "Starting data fusion",
            has_email=email_extraction is not None,
            has_ocr=ocr_extraction is not None,
        )

        # Initialize result
        result = FusedExtractionResult(
            email_extraction_available=email_extraction is not None,
            ocr_extraction_available=ocr_extraction is not None,
        )

        # Handle cases where one or both sources are missing
        if not email_extraction and not ocr_extraction:
            self.logger.warning("No extraction results available for fusion")
            result.warnings.append("No extraction data available")
            result.overall_confidence = 0.0
            result.confidence_level = "low"
            return result

        if not email_extraction:
            self.logger.info("Using OCR-only extraction (no email data)")
            return await self._use_ocr_only(ocr_extraction)

        if not ocr_extraction:
            self.logger.info("Using email-only extraction (no OCR data)")
            return await self._use_email_only(email_extraction)

        # Both sources available - perform fusion
        fields_to_merge = [
            "member_id",
            "member_name",
            "provider_name",
            "service_date",
            "receipt_number",
            "total_amount",
            "gst_sst_amount",
            "provider_address",
            "policy_number",
        ]

        for field_name in fields_to_merge:
            email_value = getattr(email_extraction, field_name, None)
            email_confidence = email_extraction.field_confidences.get(field_name, 0.0)

            ocr_value = getattr(ocr_extraction.claim, field_name, None)
            ocr_confidence = ocr_extraction.field_confidences.get(field_name, 0.0)

            # Merge field
            final_value, final_confidence, source, conflict = self._merge_field(
                field_name, email_value, email_confidence, ocr_value, ocr_confidence
            )

            # Set field value
            setattr(result, field_name, final_value)
            result.field_confidences[field_name] = final_confidence
            result.data_sources[field_name] = source

            # Track conflict if any
            if conflict:
                result.conflicts.append(conflict)
                self.logger.warning(
                    "Field conflict detected",
                    field=field_name,
                    resolution=conflict.resolution,
                )

        # Calculate overall confidence
        overall_conf, conf_level = self._calculate_overall_confidence(
            result.field_confidences
        )
        result.overall_confidence = overall_conf
        result.confidence_level = conf_level

        # Add warnings for conflicts
        if result.conflicts:
            result.warnings.append(
                f"{len(result.conflicts)} field conflict(s) resolved during fusion"
            )

        self.logger.info(
            "Data fusion complete",
            overall_confidence=result.overall_confidence,
            confidence_level=result.confidence_level,
            conflicts=len(result.conflicts),
            boosts=len(result.confidence_boosts),
        )

        return result

    def _merge_field(
        self,
        field_name: str,
        email_value: Optional[Any],
        email_confidence: float,
        ocr_value: Optional[Any],
        ocr_confidence: float,
    ) -> Tuple[Optional[Any], float, str, Optional[FieldConflict]]:
        """
        Merge a single field from email and OCR sources.

        Returns:
            Tuple of (final_value, final_confidence, source, conflict)
        """
        # Handle cases where one or both values are None
        if email_value is None and ocr_value is None:
            return None, 0.0, "none", None

        if email_value is None:
            return ocr_value, ocr_confidence, "ocr", None

        if ocr_value is None:
            return email_value, email_confidence, "email", None

        # Both values exist - check agreement
        agrees, similarity = self._check_agreement(field_name, email_value, ocr_value)

        if agrees:
            # Values agree - boost confidence
            if similarity >= 1.0:
                # Exact match
                boost = self.config.exact_match_boost
                boost_reason = "exact_match"
            else:
                # Fuzzy match
                boost = self.config.fuzzy_match_boost
                boost_reason = "fuzzy_match"

            # Use preference rules to pick base value
            if field_name in self.config.prefer_ocr_fields:
                final_value = ocr_value
                base_confidence = ocr_confidence
                source = "both (prefer_ocr)"
            elif field_name in self.config.prefer_email_fields:
                final_value = email_value
                base_confidence = email_confidence
                source = "both (prefer_email)"
            else:
                # No preference - use higher confidence
                if ocr_confidence >= email_confidence:
                    final_value = ocr_value
                    base_confidence = ocr_confidence
                    source = "both (higher_conf_ocr)"
                else:
                    final_value = email_value
                    base_confidence = email_confidence
                    source = "both (higher_conf_email)"

            # Apply boost
            final_confidence = min(
                base_confidence + boost, self.config.max_confidence
            )

            self.logger.debug(
                "Field agreement detected",
                field=field_name,
                similarity=similarity,
                boost=boost,
                reason=boost_reason,
                final_confidence=final_confidence,
            )

            return final_value, final_confidence, source, None

        # Values conflict - resolve
        conflict = self._resolve_conflict(
            field_name, email_value, email_confidence, ocr_value, ocr_confidence
        )

        if conflict.resolution == "used_email":
            return email_value, email_confidence, "email", conflict
        elif conflict.resolution == "used_ocr":
            return ocr_value, ocr_confidence, "ocr", conflict
        else:
            # used_higher_confidence
            if ocr_confidence >= email_confidence:
                return ocr_value, ocr_confidence, "ocr", conflict
            else:
                return email_value, email_confidence, "email", conflict

    def _resolve_conflict(
        self,
        field_name: str,
        email_value: Any,
        email_confidence: float,
        ocr_value: Any,
        ocr_confidence: float,
    ) -> FieldConflict:
        """
        Resolve conflict between email and OCR values.

        Returns:
            FieldConflict with resolution decision
        """
        # Apply preference rules
        if field_name in self.config.prefer_ocr_fields:
            return FieldConflict(
                field_name=field_name,
                email_value=str(email_value),
                email_confidence=email_confidence,
                ocr_value=str(ocr_value),
                ocr_confidence=ocr_confidence,
                resolution="used_ocr",
                reason=f"Field '{field_name}' prefers OCR source (receipt-specific)",
            )

        if field_name in self.config.prefer_email_fields:
            return FieldConflict(
                field_name=field_name,
                email_value=str(email_value),
                email_confidence=email_confidence,
                ocr_value=str(ocr_value),
                ocr_confidence=ocr_confidence,
                resolution="used_email",
                reason=f"Field '{field_name}' prefers email source (member-specific)",
            )

        # No preference - use higher confidence
        if ocr_confidence > email_confidence:
            resolution = "used_ocr"
            reason = f"OCR confidence ({ocr_confidence:.2f}) > email confidence ({email_confidence:.2f})"
        elif email_confidence > ocr_confidence:
            resolution = "used_email"
            reason = f"Email confidence ({email_confidence:.2f}) > OCR confidence ({ocr_confidence:.2f})"
        else:
            # Equal confidence - prefer OCR for tie-breaking
            resolution = "used_ocr"
            reason = "Equal confidence - OCR used as tie-breaker"

        return FieldConflict(
            field_name=field_name,
            email_value=str(email_value),
            email_confidence=email_confidence,
            ocr_value=str(ocr_value),
            ocr_confidence=ocr_confidence,
            resolution=resolution,
            reason=reason,
        )

    def _check_agreement(
        self, field_name: str, value1: Optional[Any], value2: Optional[Any]
    ) -> Tuple[bool, float]:
        """
        Check if two values agree (exact or fuzzy match).

        Returns:
            Tuple of (agrees, similarity_score)
        """
        if value1 is None or value2 is None:
            return False, 0.0

        # Handle datetime fields
        if isinstance(value1, datetime) and isinstance(value2, datetime):
            # Compare dates only (ignore time)
            if value1.date() == value2.date():
                return True, 1.0
            return False, 0.0

        # Handle numeric fields
        if isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
            # Allow small floating point differences
            if abs(value1 - value2) < 0.01:
                return True, 1.0
            return False, 0.0

        # Handle string fields
        str1 = str(value1).strip().lower()
        str2 = str(value2).strip().lower()

        # Exact match
        if str1 == str2:
            return True, 1.0

        # Fuzzy match
        similarity = fuzzy_match(str1, str2, self.config.fuzzy_match_threshold)

        if similarity >= self.config.fuzzy_match_threshold:
            return True, similarity

        return False, similarity

    def _calculate_overall_confidence(
        self, field_confidences: Dict[str, float]
    ) -> Tuple[float, str]:
        """
        Calculate overall confidence from field confidences.

        Returns:
            Tuple of (overall_score, confidence_level)
        """
        if not field_confidences:
            return 0.0, "low"

        # Required fields for overall confidence
        required_fields = [
            "member_id",
            "provider_name",
            "total_amount",
            "service_date",
        ]

        # Calculate weighted average
        # Required fields get 70% weight, optional fields get 30% weight
        required_confidences = [
            conf
            for field, conf in field_confidences.items()
            if field in required_fields
        ]
        optional_confidences = [
            conf
            for field, conf in field_confidences.items()
            if field not in required_fields
        ]

        if not required_confidences:
            # No required fields - use all available
            overall = sum(field_confidences.values()) / len(field_confidences)
        else:
            required_avg = sum(required_confidences) / len(required_confidences)
            optional_avg = (
                sum(optional_confidences) / len(optional_confidences)
                if optional_confidences
                else required_avg
            )
            overall = required_avg * 0.7 + optional_avg * 0.3

        # Determine confidence level
        if overall >= self.config.high_confidence_threshold:
            level = "high"
        elif overall >= self.config.medium_confidence_threshold:
            level = "medium"
        else:
            level = "low"

        return round(overall, 3), level

    async def _use_email_only(
        self, email_extraction: EmailExtractionResult
    ) -> FusedExtractionResult:
        """
        Create fused result from email extraction only.

        Args:
            email_extraction: Email parsing result

        Returns:
            FusedExtractionResult with email data
        """
        result = FusedExtractionResult(
            member_id=email_extraction.member_id,
            member_name=email_extraction.member_name,
            provider_name=email_extraction.provider_name,
            service_date=email_extraction.service_date,
            receipt_number=email_extraction.receipt_number,
            total_amount=email_extraction.total_amount,
            gst_sst_amount=email_extraction.gst_sst_amount,
            provider_address=email_extraction.provider_address,
            policy_number=email_extraction.policy_number,
            field_confidences=email_extraction.field_confidences.copy(),
            overall_confidence=email_extraction.overall_confidence,
            confidence_level=email_extraction.confidence_level,
            warnings=email_extraction.warnings.copy(),
            email_extraction_available=True,
            ocr_extraction_available=False,
        )

        # Mark all fields as email-sourced
        for field in result.field_confidences.keys():
            result.data_sources[field] = "email"

        result.warnings.append("OCR extraction not available - using email data only")

        self.logger.info(
            "Using email-only extraction",
            overall_confidence=result.overall_confidence,
            fields=len(result.field_confidences),
        )

        return result

    async def _use_ocr_only(
        self, ocr_extraction: ExtractionResult
    ) -> FusedExtractionResult:
        """
        Create fused result from OCR extraction only.

        Args:
            ocr_extraction: OCR extraction result

        Returns:
            FusedExtractionResult with OCR data
        """
        claim = ocr_extraction.claim

        result = FusedExtractionResult(
            member_id=claim.member_id,
            member_name=claim.member_name,
            provider_name=claim.provider_name,
            service_date=claim.service_date,
            receipt_number=claim.receipt_number,
            total_amount=claim.total_amount,
            gst_sst_amount=(
                claim.gst_amount if claim.gst_amount else claim.sst_amount
            ),
            provider_address=claim.provider_address,
            policy_number=claim.policy_number,
            field_confidences=ocr_extraction.field_confidences.copy(),
            overall_confidence=ocr_extraction.confidence_score,
            confidence_level=ocr_extraction.confidence_level.value,
            warnings=ocr_extraction.warnings.copy(),
            email_extraction_available=False,
            ocr_extraction_available=True,
        )

        # Mark all fields as OCR-sourced
        for field in result.field_confidences.keys():
            result.data_sources[field] = "ocr"

        result.warnings.append("Email extraction not available - using OCR data only")

        self.logger.info(
            "Using OCR-only extraction",
            overall_confidence=result.overall_confidence,
            fields=len(result.field_confidences),
        )

        return result


def fuzzy_match(
    str1: Optional[str], str2: Optional[str], threshold: float = 0.85
) -> float:
    """
    Calculate similarity between two strings.

    Uses SequenceMatcher for character-based similarity.
    Returns score from 0.0 to 1.0

    Args:
        str1: First string
        str2: Second string
        threshold: Minimum similarity threshold (not used in calculation)

    Returns:
        Similarity score (0.0 to 1.0)
    """
    if not str1 or not str2:
        return 0.0

    # Normalize strings
    s1 = str1.strip().lower()
    s2 = str2.strip().lower()

    if not s1 or not s2:
        return 0.0

    # Calculate similarity using SequenceMatcher
    similarity = SequenceMatcher(None, s1, s2).ratio()

    return similarity
