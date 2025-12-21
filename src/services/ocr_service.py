"""OCR service using PaddleOCR-VL."""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from paddleocr import PaddleOCR

from src.config.settings import settings
from src.models.claim import ExtractedClaim
from src.models.extraction import ExtractionResult, OCRResult
from src.utils.confidence import (
    calculate_field_confidence,
    calculate_overall_confidence,
    get_confidence_level,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class OCRService:
    """PaddleOCR-VL integration for text extraction."""

    def __init__(self) -> None:
        """Initialize OCR engine."""
        self.config = settings.ocr
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang=self.config.default_language,
            use_gpu=self.config.use_gpu,
            show_log=False,
            det_db_thresh=self.config.detection_threshold,
            rec_batch_num=self.config.batch_size,
        )
        logger.info(
            "OCR initialized",
            gpu_enabled=self.config.use_gpu,
            language=self.config.default_language,
        )

    async def extract_text(self, image_path: Path) -> OCRResult:
        """
        Extract raw text from image using OCR.

        Args:
            image_path: Path to image file

        Returns:
            OCRResult with text blocks and metadata
        """
        logger.info("Starting OCR extraction", file=str(image_path))
        start_time = datetime.now()

        try:
            result = self.ocr.ocr(str(image_path), cls=True)

            # Extract text blocks with positions and scores
            text_blocks = []
            if result and result[0]:
                for line in result[0]:
                    text_blocks.append(
                        {
                            "text": line[1][0],
                            "confidence": float(line[1][1]),
                            "position": line[0],
                        }
                    )

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                "OCR extraction complete",
                blocks_found=len(text_blocks),
                processing_time_ms=processing_time,
            )

            return OCRResult(
                text_blocks=text_blocks,
                detected_language=self.config.default_language,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error("OCR extraction failed", error=str(e), file=str(image_path))
            raise

    async def extract_structured_data(self, image_path: Path) -> ExtractionResult:
        """
        Extract and structure claim data from receipt image.

        Args:
            image_path: Path to receipt image

        Returns:
            ExtractionResult with structured claim and confidence
        """
        # Extract raw text
        ocr_result = await self.extract_text(image_path)

        # Combine all text
        full_text = " ".join([block["text"] for block in ocr_result.text_blocks])
        avg_confidence = (
            sum(block["confidence"] for block in ocr_result.text_blocks)
            / len(ocr_result.text_blocks)
            if ocr_result.text_blocks
            else 0.0
        )

        # Extract structured fields
        claim = ExtractedClaim(raw_text=full_text)
        field_scores = {}

        # Extract member ID
        member_id = self._extract_member_id(full_text, ocr_result.text_blocks)
        if member_id:
            claim.member_id = member_id
            field_scores["member_id"] = calculate_field_confidence(member_id, avg_confidence)

        # Extract provider name
        provider = self._extract_provider_name(full_text, ocr_result.text_blocks)
        if provider:
            claim.provider_name = provider
            field_scores["provider_name"] = calculate_field_confidence(
                provider, avg_confidence
            )

        # Extract total amount
        amount = self._extract_amount(full_text, ocr_result.text_blocks)
        if amount:
            claim.total_amount = amount
            field_scores["total_amount"] = calculate_field_confidence(amount, avg_confidence)

        # Extract date
        service_date = self._extract_date(full_text, ocr_result.text_blocks)
        if service_date:
            claim.service_date = service_date
            field_scores["service_date"] = calculate_field_confidence(
                service_date, avg_confidence
            )

        # Extract receipt number
        receipt_num = self._extract_receipt_number(full_text, ocr_result.text_blocks)
        if receipt_num:
            claim.receipt_number = receipt_num
            field_scores["receipt_number"] = calculate_field_confidence(
                receipt_num, avg_confidence
            )

        # Calculate overall confidence
        overall_confidence = calculate_overall_confidence(claim, field_scores)
        confidence_level = get_confidence_level(overall_confidence)

        # Generate warnings
        warnings = []
        if claim.total_amount is None:
            warnings.append("Amount field not detected")
        if claim.member_id is None:
            warnings.append("Member ID not found")
        if overall_confidence < 0.75:
            warnings.append("Low confidence on overall extraction")

        return ExtractionResult(
            claim=claim,
            confidence_score=overall_confidence,
            confidence_level=confidence_level,
            field_confidences=field_scores,
            warnings=warnings,
            ocr_result=ocr_result,
        )

    def _extract_member_id(self, text: str, blocks: list[dict]) -> Optional[str]:
        """Extract member ID from text."""
        patterns = [
            r"Member\s*ID[:\s]+([A-Z0-9]+)",
            r"Member[:\s]+([A-Z0-9]+)",
            r"Policy\s*No[:\s]+([A-Z0-9]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_provider_name(self, text: str, blocks: list[dict]) -> Optional[str]:
        """Extract provider/clinic name from text."""
        # Usually at the top of receipt
        if blocks:
            # Take first few high-confidence lines
            candidates = [b["text"] for b in blocks[:5] if b["confidence"] > 0.8]
            if candidates:
                return candidates[0]
        return None

    def _extract_amount(self, text: str, blocks: list[dict]) -> Optional[float]:
        """Extract total amount from text."""
        patterns = [
            r"Total[:\s]+RM\s*(\d+\.?\d*)",
            r"Amount[:\s]+RM\s*(\d+\.?\d*)",
            r"Grand\s*Total[:\s]+RM\s*(\d+\.?\d*)",
            r"RM\s*(\d+\.\d{2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None

    def _extract_date(self, text: str, blocks: list[dict]) -> Optional[datetime]:
        """Extract service date from text."""
        patterns = [
            r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",  # DD/MM/YYYY or DD-MM-YYYY
            r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",  # YYYY/MM/DD
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    # Assume DD/MM/YYYY format (Malaysian standard)
                    day, month, year = int(match.group(1)), int(match.group(2)), int(
                        match.group(3)
                    )
                    return datetime(year, month, day)
                except (ValueError, IndexError):
                    continue
        return None

    def _extract_receipt_number(self, text: str, blocks: list[dict]) -> Optional[str]:
        """Extract receipt number from text."""
        patterns = [
            r"Receipt\s*No[:\s]+([A-Z0-9-]+)",
            r"Invoice\s*No[:\s]+([A-Z0-9-]+)",
            r"Ref[:\s]+([A-Z0-9-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
