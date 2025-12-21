"""Confidence scoring utilities for OCR extraction."""

from typing import Any

from src.models.claim import ExtractedClaim
from src.models.extraction import ConfidenceLevel


def calculate_field_confidence(field_value: Any, ocr_score: float) -> float:
    """
    Calculate confidence for a single field.

    Args:
        field_value: Extracted field value
        ocr_score: Raw OCR confidence score

    Returns:
        Confidence score (0.0-1.0)
    """
    if field_value is None or (isinstance(field_value, str) and not field_value.strip()):
        return 0.0

    # Start with OCR score
    confidence = ocr_score

    # Penalty for very short values (likely incomplete)
    if isinstance(field_value, str) and len(field_value) < 3:
        confidence *= 0.8

    return min(1.0, max(0.0, confidence))


def calculate_overall_confidence(
    claim: ExtractedClaim, field_scores: dict[str, float]
) -> float:
    """
    Calculate overall confidence score for claim.

    Args:
        claim: Extracted claim data
        field_scores: Individual field confidence scores

    Returns:
        Overall confidence score (0.0-1.0)
    """
    # Required fields with weights
    required_fields = {
        "member_id": 0.25,
        "member_name": 0.15,
        "provider_name": 0.15,
        "service_date": 0.15,
        "receipt_number": 0.10,
        "total_amount": 0.20,
    }

    total_weight = 0.0
    weighted_score = 0.0

    for field, weight in required_fields.items():
        field_value = getattr(claim, field, None)
        if field_value is not None:
            field_confidence = field_scores.get(field, 0.5)
            weighted_score += field_confidence * weight
            total_weight += weight

    # If no fields extracted, return 0
    if total_weight == 0:
        return 0.0

    # Normalize to 0-1
    overall = weighted_score / total_weight

    # Penalty if critical fields missing
    if claim.member_id is None or claim.total_amount is None:
        overall *= 0.6

    return min(1.0, max(0.0, overall))


def get_confidence_level(score: float) -> ConfidenceLevel:
    """
    Get confidence level classification.

    Args:
        score: Confidence score (0.0-1.0)

    Returns:
        ConfidenceLevel enum value
    """
    if score >= 0.90:
        return ConfidenceLevel.HIGH
    elif score >= 0.75:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW
