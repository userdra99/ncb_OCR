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
from src.utils.pdf_utils import cleanup_pdf_images, pdf_to_images

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
            det_db_thresh=self.config.detection_threshold,
            rec_batch_num=self.config.batch_size,
            show_log=False,
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

            # Detect languages present in the text
            full_text = " ".join([block["text"] for block in text_blocks])
            detected_languages = self._detect_languages(full_text)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                "OCR extraction complete",
                blocks_found=len(text_blocks),
                processing_time_ms=processing_time,
                detected_languages=detected_languages,
            )

            return OCRResult(
                text_blocks=text_blocks,
                detected_language=", ".join(detected_languages) if detected_languages else self.config.default_language,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error("OCR extraction failed", error=str(e), file=str(image_path))
            raise

    async def extract_structured_data(self, file_path: Path) -> ExtractionResult:
        """
        Extract and structure claim data from receipt image or PDF.

        Args:
            file_path: Path to receipt image or PDF file

        Returns:
            ExtractionResult with structured claim and confidence
        """
        # Convert Path to pathlib.Path if string
        file_path = Path(file_path) if isinstance(file_path, str) else file_path

        # Handle PDF files
        if file_path.suffix.lower() == '.pdf':
            logger.info("Processing PDF file", file_path=str(file_path))
            return await self._extract_from_pdf(file_path)

        # Handle image files
        return await self._extract_from_image(file_path)

    async def _extract_from_image(self, image_path: Path) -> ExtractionResult:
        """
        Extract and structure claim data from a single receipt image.

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

        # Extract member ID and policy number
        member_id = self._extract_member_id(full_text, ocr_result.text_blocks)
        if member_id:
            claim.member_id = member_id
            field_scores["member_id"] = calculate_field_confidence(member_id, avg_confidence)

        # Extract member name
        member_name = self._extract_member_name(full_text, ocr_result.text_blocks)
        if member_name:
            claim.member_name = member_name
            field_scores["member_name"] = calculate_field_confidence(member_name, avg_confidence)

        # Extract policy number (may be same as member_id or separate)
        policy_number = self._extract_policy_number(full_text, ocr_result.text_blocks)
        if policy_number:
            claim.policy_number = policy_number
            field_scores["policy_number"] = calculate_field_confidence(policy_number, avg_confidence)
        elif member_id:
            # Fallback: use member_id as policy_number if not found separately
            claim.policy_number = member_id
            field_scores["policy_number"] = field_scores.get("member_id", avg_confidence)

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

        # Extract GST/SST amount
        gst_sst_amount = self._extract_gst_sst_amount(full_text, ocr_result.text_blocks)
        if gst_sst_amount:
            # Determine if it's GST or SST based on context
            # GST was 6% (pre-2018), SST is 10% (current)
            # For now, store as SST (current standard in Malaysia)
            claim.sst_amount = gst_sst_amount
            field_scores["sst_amount"] = calculate_field_confidence(gst_sst_amount, avg_confidence)

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

    async def _extract_from_pdf(self, pdf_path: Path) -> ExtractionResult:
        """
        Extract and structure claim data from PDF (converts to images first).

        Args:
            pdf_path: Path to PDF file

        Returns:
            ExtractionResult with structured claim and confidence
        """
        image_paths = []
        try:
            # Convert PDF to images
            logger.info("Converting PDF to images", pdf_path=str(pdf_path))
            image_paths = pdf_to_images(pdf_path)

            if not image_paths:
                logger.warning("No images extracted from PDF", pdf_path=str(pdf_path))
                raise ValueError("PDF conversion produced no images")

            # Process each page
            all_text_blocks = []
            all_ocr_results = []

            for idx, image_path in enumerate(image_paths, 1):
                logger.info(f"Processing page {idx}/{len(image_paths)}", image=str(image_path))
                ocr_result = await self.extract_text(image_path)
                all_text_blocks.extend(ocr_result.text_blocks)
                all_ocr_results.append(ocr_result)

            # Combine text from all pages
            full_text = " ".join([block["text"] for block in all_text_blocks])
            avg_confidence = (
                sum(block["confidence"] for block in all_text_blocks)
                / len(all_text_blocks)
                if all_text_blocks
                else 0.0
            )

            logger.info(
                "PDF OCR complete",
                total_pages=len(image_paths),
                total_blocks=len(all_text_blocks),
                avg_confidence=avg_confidence,
            )

            # Extract structured fields (same as image processing)
            claim = ExtractedClaim(raw_text=full_text)
            field_scores = {}

            # Extract member ID and policy number
            member_id = self._extract_member_id(full_text, all_text_blocks)
            if member_id:
                claim.member_id = member_id
                field_scores["member_id"] = calculate_field_confidence(member_id, avg_confidence)

            # Extract member name
            member_name = self._extract_member_name(full_text, all_text_blocks)
            if member_name:
                claim.member_name = member_name
                field_scores["member_name"] = calculate_field_confidence(member_name, avg_confidence)

            # Extract policy number (may be same as member_id or separate)
            policy_number = self._extract_policy_number(full_text, all_text_blocks)
            if policy_number:
                claim.policy_number = policy_number
                field_scores["policy_number"] = calculate_field_confidence(policy_number, avg_confidence)
            elif member_id:
                # Fallback: use member_id as policy_number if not found separately
                claim.policy_number = member_id
                field_scores["policy_number"] = field_scores.get("member_id", avg_confidence)

            # Extract provider name
            provider = self._extract_provider_name(full_text, all_text_blocks)
            if provider:
                claim.provider_name = provider
                field_scores["provider_name"] = calculate_field_confidence(provider, avg_confidence)

            # Extract total amount
            amount = self._extract_amount(full_text, all_text_blocks)
            if amount:
                claim.total_amount = amount
                field_scores["total_amount"] = calculate_field_confidence(amount, avg_confidence)

            # Extract GST/SST amount
            gst_sst_amount = self._extract_gst_sst_amount(full_text, all_text_blocks)
            if gst_sst_amount:
                claim.sst_amount = gst_sst_amount
                field_scores["sst_amount"] = calculate_field_confidence(gst_sst_amount, avg_confidence)

            # Extract date
            service_date = self._extract_date(full_text, all_text_blocks)
            if service_date:
                claim.service_date = service_date
                field_scores["service_date"] = calculate_field_confidence(service_date, avg_confidence)

            # Extract receipt number
            receipt_num = self._extract_receipt_number(full_text, all_text_blocks)
            if receipt_num:
                claim.receipt_number = receipt_num
                field_scores["receipt_number"] = calculate_field_confidence(receipt_num, avg_confidence)

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
            if len(image_paths) > 1:
                warnings.append(f"Multi-page PDF ({len(image_paths)} pages)")

            # Use first page's OCR result as representative
            return ExtractionResult(
                claim=claim,
                confidence_score=overall_confidence,
                confidence_level=confidence_level,
                field_confidences=field_scores,
                warnings=warnings,
                ocr_result=all_ocr_results[0] if all_ocr_results else None,
            )

        finally:
            # Cleanup temporary image files
            if image_paths:
                logger.info("Cleaning up PDF temp files", count=len(image_paths))
                cleanup_pdf_images(image_paths)

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
        """
        Extract provider/clinic name from text.

        Handles:
        - Malaysian clinic and hospital naming patterns
        - Multi-language names (English, Malay, Chinese, Tamil)
        - Common prefixes: Klinik, Clinic, Hospital, Pusat, Centre
        """
        # Common Malaysian healthcare provider patterns
        provider_patterns = [
            # Explicit labels
            r"(?:Provider|Clinic|Hospital|Klinik)[:\s]+([A-Z][A-Za-z\s&.,'-]+)",

            # Common naming patterns (at start of line)
            r"^((?:Klinik|Clinic|Pusat|Centre|Center|Hospital|Hospitel)\s+[A-Z][A-Za-z\s&.,'-]+)",

            # Medical facility identifiers
            r"((?:Klinik\s+Pergigian|Dental\s+Clinic|Medical\s+Centre|Pusat\s+Perubatan)\s+[A-Za-z\s&.,'-]+)",
        ]

        # Try pattern matching first
        for pattern in provider_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = match.group(1).strip()
                # Validate (5-100 chars, contains letters)
                if 5 <= len(name) <= 100 and any(c.isalpha() for c in name):
                    # Clean up multiple spaces
                    name = " ".join(name.split())
                    logger.info("Provider name extracted from pattern", name=name)
                    return name

        # Fallback: Use first few high-confidence lines
        if blocks:
            # Look for capitalised text in first 10 blocks
            for block in blocks[:10]:
                text_content = block["text"].strip()
                confidence = block["confidence"]

                # Skip if too short or too long
                if not (5 <= len(text_content) <= 100):
                    continue

                # High confidence block with capital letters and common keywords
                if confidence > 0.85:
                    # Check for healthcare keywords
                    keywords = ["klinik", "clinic", "hospital", "medical", "dental", "pusat", "centre", "center"]
                    text_lower = text_content.lower()

                    if any(keyword in text_lower for keyword in keywords):
                        logger.info(
                            "Provider name extracted from high-confidence block",
                            name=text_content,
                            confidence=confidence,
                        )
                        return text_content

            # Last resort: take first high-confidence line
            candidates = [b["text"].strip() for b in blocks[:5] if b["confidence"] > 0.8]
            if candidates:
                logger.info("Provider name extracted from first line", name=candidates[0])
                return candidates[0]

        logger.debug("No provider name found")
        return None

    def _extract_amount(self, text: str, blocks: list[dict]) -> Optional[float]:
        """
        Extract total amount from text.

        Handles Malaysian receipt formats including:
        - RM prefix with/without space
        - Comma thousands separators
        - GST/SST inclusive amounts
        - Multiple currency formats
        """
        patterns = [
            # Explicit total labels (highest priority)
            r"(?:Total|Jumlah|总额|மொத்தம்)[:\s]+RM\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
            r"(?:Grand\s*Total|Total\s*Amount|Jumlah\s*Keseluruhan)[:\s]+RM\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
            r"(?:Amount\s*Payable|Amaun\s*Perlu\s*Dibayar)[:\s]+RM\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
            r"(?:Net\s*Total|Total\s*Bersih)[:\s]+RM\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",

            # With GST/SST context
            r"(?:Total\s*(?:Inc|Including|Termasuk)\s*(?:GST|SST))[:\s]+RM\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",

            # RM with amount (fallback - takes largest amount)
            r"RM\s*(\d{1,3}(?:,\d{3})*\.\d{2})",
            r"RM(\d+\.\d{2})",
        ]

        amounts = []
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    # Remove commas from number
                    amount_str = match.group(1).replace(",", "")
                    amount = float(amount_str)
                    if 0 < amount < 1000000:  # Sanity check
                        amounts.append((amount, pattern))
                        logger.debug(
                            "Amount candidate found",
                            amount=amount,
                            pattern=pattern,
                        )
                except (ValueError, IndexError):
                    continue

        # Return first (highest priority pattern) or largest amount
        if amounts:
            # Prioritize first match from explicit labels
            return amounts[0][0]

        logger.warning("No amount found in receipt", text_length=len(text))
        return None

    def _extract_date(self, text: str, blocks: list[dict]) -> Optional[datetime]:
        """
        Extract service date from text.

        Handles Malaysian date formats:
        - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY (standard Malaysian)
        - D/M/YYYY (single digit days/months)
        - YYYY/MM/DD (less common)
        - Month names in English and Malay
        """
        # Pattern: DD/MM/YYYY with various separators
        date_patterns = [
            # Explicit date labels (highest priority)
            (r"(?:Date|Tarikh|日期|தேதி)[:\s]+(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", "DMY", True),
            (r"(?:Service\s*Date|Tarikh\s*Perkhidmatan)[:\s]+(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", "DMY", True),

            # Standard Malaysian DD/MM/YYYY
            (r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", "DMY", False),

            # YYYY/MM/DD format
            (r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})", "YMD", False),

            # Month name formats (e.g., "15 Jan 2024" or "15 Januari 2024")
            (r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mac|Mar(?:ch)?|Apr(?:il)?|Mei|May|Jun|Jul(?:y)?|Ogos|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Okt(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|Dis(?:ember)?)\s+(\d{4})", "DMY_NAME", False),
        ]

        month_map = {
            # English
            "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
            "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
            "nov": 11, "november": 11, "dec": 12, "december": 12,
            # Malay
            "mac": 3, "mei": 5, "ogos": 8, "okt": 10, "oktober": 10, "dis": 12, "disember": 12,
        }

        for pattern, format_type, is_labeled in date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    if format_type == "DMY":
                        day = int(match.group(1))
                        month = int(match.group(2))
                        year = int(match.group(3))
                    elif format_type == "YMD":
                        year = int(match.group(1))
                        month = int(match.group(2))
                        day = int(match.group(3))
                    elif format_type == "DMY_NAME":
                        day = int(match.group(1))
                        month_name = match.group(2).lower()
                        month = month_map.get(month_name, month_map.get(month_name[:3], 0))
                        year = int(match.group(3))
                        if month == 0:
                            continue

                    # Validate date ranges
                    if not (1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100):
                        logger.debug(
                            "Date validation failed",
                            day=day,
                            month=month,
                            year=year,
                        )
                        continue

                    # Try to create datetime
                    extracted_date = datetime(year, month, day)

                    # Prefer labeled dates
                    if is_labeled:
                        logger.info(
                            "Date extracted from label",
                            date=extracted_date.strftime("%Y-%m-%d"),
                        )
                        return extracted_date

                    # Check if date is reasonable (not in future, not too old)
                    current_date = datetime.now()
                    if extracted_date <= current_date and (current_date - extracted_date).days < 365 * 2:
                        logger.info(
                            "Date extracted",
                            date=extracted_date.strftime("%Y-%m-%d"),
                        )
                        return extracted_date
                    else:
                        logger.debug(
                            "Date rejected (out of reasonable range)",
                            date=extracted_date.strftime("%Y-%m-%d"),
                        )

                except (ValueError, IndexError) as e:
                    logger.debug("Date parse failed", error=str(e))
                    continue

        logger.warning("No valid date found in receipt")
        return None

    def _extract_receipt_number(self, text: str, blocks: list[dict]) -> Optional[str]:
        """Extract receipt/invoice number from text."""
        patterns = [
            r"Receipt\s*No[:\s]+([A-Z0-9-]+)",
            r"Invoice\s*No[:\s]+([A-Z0-9-]+)",
            r"Invoice\s*Number[:\s]+([A-Z0-9-]+)",
            r"Ref[:\s]+([A-Z0-9-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_policy_number(self, text: str, blocks: list[dict]) -> Optional[str]:
        """Extract policy number from text."""
        patterns = [
            r"Policy\s*No[:\s]+([A-Z0-9]+)",
            r"Policy\s*Number[:\s]+([A-Z0-9]+)",
            r"Member\s*Policy[:\s]+([A-Z0-9]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_gst_sst_amount(self, text: str, blocks: list[dict]) -> Optional[float]:
        """
        Extract GST/SST tax amount separately from receipt.

        Handles:
        - GST at 6% (pre-2018)
        - SST at 10% (current)
        - Multiple tax formats
        """
        patterns = [
            # Explicit tax labels
            r"(?:GST|SST)\s*(?:6%|10%|@6%|@10%)?[:\s]+RM\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
            r"(?:Tax|Cukai)[:\s]+RM\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
            r"(?:Service\s*Tax|Cukai\s*Perkhidmatan)[:\s]+RM\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",

            # With percentage
            r"(?:GST|SST)\s*\((?:6|10)%\)[:\s]+RM\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    # Remove commas from number
                    amount_str = match.group(1).replace(",", "")
                    tax_amount = float(amount_str)
                    if 0 < tax_amount < 100000:  # Sanity check
                        logger.info(
                            "GST/SST amount extracted",
                            tax_amount=tax_amount,
                            pattern=pattern,
                        )
                        return tax_amount
                except (ValueError, IndexError):
                    continue

        logger.debug("No GST/SST amount found")
        return None

    def _extract_member_name(self, text: str, blocks: list[dict]) -> Optional[str]:
        """
        Extract member/patient name from receipt.

        Handles:
        - English, Malay, Chinese, and Tamil names
        - Multiple name formats
        - Common Malaysian name patterns
        """
        patterns = [
            # Explicit labels (multi-language)
            r"(?:Patient\s*Name|Member\s*Name|Nama\s*Pesakit|Nama)[:\s]+([A-Z][A-Za-z\s.'-]+(?:\s+(?:bin|binti|a\/l|a\/p|s\/o|d\/o)\s+[A-Za-z\s.'-]+)?)",
            r"(?:Name|Nama|姓名|பெயர்)[:\s]+([A-Z][A-Za-z\s.'-]+)",

            # IC/NRIC context (name usually nearby)
            r"(?:IC|NRIC|MyKad)[:\s]+\d+-\d+-\d+\s+([A-Z][A-Za-z\s.'-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Validate name (2-50 chars, starts with capital, contains letters)
                if 2 <= len(name) <= 50 and any(c.isalpha() for c in name):
                    # Clean up multiple spaces
                    name = " ".join(name.split())
                    logger.info(
                        "Member name extracted",
                        name=name,
                    )
                    return name

        logger.debug("No member name found")
        return None

    def _detect_languages(self, text: str) -> list[str]:
        """
        Detect languages present in receipt text.

        Handles Malaysian multilingual receipts:
        - English (Latin alphabet)
        - Malay (Latin alphabet with specific words)
        - Chinese (汉字/中文)
        - Tamil (தமிழ்)

        Returns:
            List of detected language codes
        """
        languages = set()

        # Check for English/Malay (both use Latin script)
        if re.search(r"[A-Za-z]", text):
            # Look for Malay-specific words
            malay_keywords = [
                "klinik", "pusat", "perubatan", "nama", "tarikh", "jumlah",
                "pesakit", "amaun", "keseluruhan", "termasuk", "cukai",
                "perkhidmatan", "bayar", "bersih", "bil", "resit"
            ]
            if any(keyword in text.lower() for keyword in malay_keywords):
                languages.add("Malay")
            else:
                languages.add("English")

        # Check for Chinese characters (CJK Unified Ideographs)
        if re.search(r"[\u4e00-\u9fff]", text):
            languages.add("Chinese")

        # Check for Tamil script
        if re.search(r"[\u0b80-\u0bff]", text):
            languages.add("Tamil")

        detected = list(languages)
        if detected:
            logger.info("Languages detected", languages=detected)
        else:
            logger.debug("No specific languages detected, defaulting to English")
            detected = ["English"]

        return detected
