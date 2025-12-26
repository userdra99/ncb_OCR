"""
Email subject and body text parsing for claim data extraction.

This module implements parsers for extracting structured claim data
from email subject lines and body text using regex patterns optimized
for Malaysian contexts.
"""

import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from dateutil import parser as date_parser
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmailFieldExtraction(BaseModel):
    """Single extracted field with confidence score.

    Attributes:
        field_name: Name of the extracted field (e.g., 'member_id', 'amount')
        value: Extracted value, None if not found
        confidence: Confidence score from 0.0 to 1.0
        extraction_method: Method used for extraction (e.g., 'regex', 'spacy')
    """
    field_name: str
    value: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    extraction_method: str = "regex"


class SubjectParser:
    """Parse structured claim data from email subject lines.

    Uses regex patterns optimized for Malaysian receipt/invoice formats.
    Supports multiple variations of member IDs, amounts, receipt numbers,
    and provider names commonly found in Malaysian healthcare contexts.

    Example:
        >>> parser = SubjectParser()
        >>> extractions = parser.extract_from_subject(
        ...     "Member ID: M12345 - Dr. Tan Clinic Receipt RM150.00"
        ... )
        >>> extractions['member_id'].value
        'M12345'
        >>> extractions['member_id'].confidence
        0.85
    """

    # Compile regex patterns for performance
    PATTERNS = {
        # Member ID patterns: M12345, ABC123, PT001234, etc.
        # Matches: "Member ID: M12345", "Patient No: ABC123", "Policy: PT001234"
        'member_id': re.compile(
            r'(?:member|patient|policy)\s*(?:id|no|number)?:?\s*([A-Z]{1,3}\d{4,10})',
            re.IGNORECASE
        ),

        # Amount patterns: RM150.00, RM 1,500.50, RM1500
        # Matches Malaysian Ringgit with optional spacing and thousand separators
        'amount': re.compile(
            r'RM\s*([\d,]+\.?\d{0,2})',
            re.IGNORECASE
        ),

        # Receipt/Invoice number patterns: REC123, INV-2024-001, BILL/001/2024
        # Matches various receipt number formats
        'receipt_number': re.compile(
            r'(?:receipt|invoice|bill)\s*(?:no|number)?:?\s*([A-Z0-9\-/]+)',
            re.IGNORECASE
        ),

        # Provider name patterns: Dr. Tan Clinic, Klinik ABC, Hospital XYZ
        # Matches Malaysian clinic/hospital naming conventions
        'provider_name': re.compile(
            r'(?:clinic|hospital|klinik|dr\.)\s*([A-Za-z\s.&\-]+?)(?:\s*(?:receipt|invoice|bill|rm|\d|$))',
            re.IGNORECASE
        )
    }

    # Confidence scores based on match quality
    CONFIDENCE_EXACT_MATCH = 0.85  # Strong pattern match with context
    CONFIDENCE_PARTIAL_MATCH = 0.70  # Match found but weak context
    CONFIDENCE_NO_MATCH = 0.0  # No match found

    @classmethod
    def extract_from_subject(cls, subject: str) -> dict[str, EmailFieldExtraction]:
        """
        Extract claim fields from email subject line.

        Uses regex patterns to identify member IDs, amounts, receipt numbers,
        and provider names. Returns confidence scores for each extraction.

        Args:
            subject: Email subject line to parse

        Returns:
            Dictionary mapping field names to EmailFieldExtraction objects.
            Always returns all fields, even if not found (with confidence=0.0).

        Example:
            >>> subject = "Member ID: M12345 - Dr. Tan Clinic Receipt RM150.00"
            >>> extractions = SubjectParser.extract_from_subject(subject)
            >>> len(extractions)
            4
            >>> extractions['member_id'].value
            'M12345'
            >>> extractions['amount'].value
            '150.00'
        """
        if not subject or not subject.strip():
            logger.warning("Empty subject line provided to SubjectParser")
            return cls._empty_extractions()

        logger.debug(f"Parsing subject line: {subject}")

        extractions = {}

        # Extract each field using corresponding regex pattern
        for field_name, pattern in cls.PATTERNS.items():
            extraction = cls._extract_field(
                field_name=field_name,
                subject=subject,
                pattern=pattern
            )
            extractions[field_name] = extraction

            if extraction.value:
                logger.info(
                    f"Extracted {field_name}",
                    extra={
                        "field_name": field_name,
                        "value": extraction.value,
                        "confidence": extraction.confidence
                    }
                )

        return extractions

    @classmethod
    def _extract_field(
        cls,
        field_name: str,
        subject: str,
        pattern: re.Pattern
    ) -> EmailFieldExtraction:
        """
        Extract a single field using regex pattern.

        Args:
            field_name: Name of field to extract
            subject: Subject line to search
            pattern: Compiled regex pattern

        Returns:
            EmailFieldExtraction with value and confidence score
        """
        match = pattern.search(subject)

        if not match:
            return EmailFieldExtraction(
                field_name=field_name,
                value=None,
                confidence=cls.CONFIDENCE_NO_MATCH,
                extraction_method="regex"
            )

        # Extract the captured group (first group in all patterns)
        raw_value = match.group(1).strip()

        # Clean and normalize the extracted value
        cleaned_value = cls._clean_value(field_name, raw_value)

        # Calculate confidence based on match quality
        confidence = cls._calculate_confidence(field_name, match, subject)

        return EmailFieldExtraction(
            field_name=field_name,
            value=cleaned_value,
            confidence=confidence,
            extraction_method="regex"
        )

    @classmethod
    def _clean_value(cls, field_name: str, raw_value: str) -> str:
        """
        Clean and normalize extracted values.

        Args:
            field_name: Type of field (determines cleaning strategy)
            raw_value: Raw extracted value

        Returns:
            Cleaned and normalized value
        """
        if field_name == 'amount':
            # Remove thousand separators from amounts
            # "1,500.50" -> "1500.50"
            return raw_value.replace(',', '')

        elif field_name == 'provider_name':
            # Clean up provider names
            # Remove trailing punctuation and extra whitespace
            cleaned = raw_value.strip()
            # Collapse multiple spaces
            cleaned = ' '.join(cleaned.split())
            # Remove trailing periods/commas
            cleaned = cleaned.rstrip('.,')
            return cleaned

        elif field_name == 'member_id':
            # Uppercase member IDs for consistency
            return raw_value.upper()

        elif field_name == 'receipt_number':
            # Uppercase receipt numbers for consistency
            return raw_value.upper()

        return raw_value.strip()

    @classmethod
    def _calculate_confidence(
        cls,
        field_name: str,
        match: re.Match,
        subject: str
    ) -> float:
        """
        Calculate confidence score for a regex match.

        Confidence is based on:
        - Pattern specificity (exact match vs partial)
        - Context keywords present in subject
        - Length and format of extracted value

        Args:
            field_name: Type of field extracted
            match: Regex match object
            subject: Full subject line for context

        Returns:
            Confidence score from 0.0 to 1.0
        """
        # Start with exact match confidence
        confidence = cls.CONFIDENCE_EXACT_MATCH

        # Adjust based on field-specific criteria
        extracted_value = match.group(1).strip()

        if field_name == 'member_id':
            # Lower confidence if member ID seems too short or too long
            if len(extracted_value) < 4:
                confidence = cls.CONFIDENCE_PARTIAL_MATCH
            elif len(extracted_value) > 15:
                confidence = cls.CONFIDENCE_PARTIAL_MATCH

        elif field_name == 'amount':
            # Check if amount format is valid
            try:
                # Remove commas and validate number
                amount_str = extracted_value.replace(',', '')
                amount_float = float(amount_str)
                # Suspiciously low or high amounts reduce confidence
                if amount_float < 1.0 or amount_float > 1000000.0:
                    confidence = cls.CONFIDENCE_PARTIAL_MATCH
            except ValueError:
                confidence = cls.CONFIDENCE_PARTIAL_MATCH

        elif field_name == 'receipt_number':
            # Receipt numbers should be alphanumeric
            if len(extracted_value) < 3:
                confidence = cls.CONFIDENCE_PARTIAL_MATCH

        elif field_name == 'provider_name':
            # Provider names should have reasonable length
            if len(extracted_value) < 3 or len(extracted_value) > 100:
                confidence = cls.CONFIDENCE_PARTIAL_MATCH
            # Higher confidence if common Malaysian provider keywords present
            provider_lower = extracted_value.lower()
            if any(keyword in provider_lower for keyword in ['clinic', 'klinik', 'hospital', 'dr', 'medical']):
                confidence = cls.CONFIDENCE_EXACT_MATCH

        return confidence

    @classmethod
    def _empty_extractions(cls) -> dict[str, EmailFieldExtraction]:
        """
        Return empty extractions for all fields.

        Used when subject line is empty or invalid.

        Returns:
            Dictionary with all fields having None values and 0.0 confidence
        """
        return {
            field_name: EmailFieldExtraction(
                field_name=field_name,
                value=None,
                confidence=cls.CONFIDENCE_NO_MATCH,
                extraction_method="regex"
            )
            for field_name in cls.PATTERNS.keys()
        }


class BodyTextParser:
    """Extract claim fields from email body text using Malaysian-specific patterns.

    This parser handles comprehensive field extraction from email body text,
    supporting Malaysian date formats (DD/MM/YYYY), currency (RM), and
    multi-language keywords (English, Malay).

    Features:
        - Extracts all required claim fields (member_id, member_name, etc.)
        - Handles Malaysian date formats with DD/MM/YYYY convention
        - Parses RM currency with thousand separators
        - Supports English and Malay keywords
        - Provides confidence scoring for each extraction
        - Includes fallback patterns for robustness

    Example:
        >>> body = '''
        ... Member Name: Ahmad bin Ali
        ... Service Date: 15/12/2024
        ... Provider: Klinik Kesihatan ABC
        ... Total: RM 150.50
        ... '''
        >>> extractions = await BodyTextParser.extract_from_body(body)
        >>> extractions['member_name'].value
        'Ahmad bin Ali'
        >>> extractions['total_amount'].value
        '150.50'
    """

    # Malaysian-specific regex patterns for body text
    PATTERNS = {
        # Member ID: Various formats (MEM123456, M-123456, etc.)
        # Matches: "Member ID: M12345", "Patient No: 123456"
        "member_id": re.compile(
            r"(?:member|patient|pesakit)\s*(?:id|no|number)?:?\s*([A-Z]?[\-\s]?\d{6,10})",
            re.IGNORECASE,
        ),

        # Member Name: Capitalized names (English and Malay)
        # Handles: bin/binti, a/l, a/p (Malaysian naming conventions)
        "member_name": re.compile(
            r"(?:member|patient|pesakit|name)\s*(?:name)?:?\s*([A-Z][a-z]+(?:\s+(?:bin|binti|a\/l|a\/p)?\s*[A-Z][a-z]+)+)",
            re.IGNORECASE,
        ),

        # Provider Name: Clinic/Hospital name
        # Handles: Klinik, Clinic, Hospital, Sdn Bhd
        "provider_name": re.compile(
            r"(?:provider|clinic|hospital|klinik|facility|from):?\s*([A-Z][A-Za-z\s&\-]+(?:Clinic|Hospital|Klinik|Centre|Center|Sdn\.?\s*Bhd\.?)?)",
            re.IGNORECASE,
        ),

        # Service Date: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
        "service_date": re.compile(
            r"(?:date|tarikh|service\s*date|visit\s*date|on):?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            re.IGNORECASE,
        ),

        # Receipt/Invoice Number
        "receipt_number": re.compile(
            r"(?:receipt|invoice|bill|no|number|nombor):?\s*#?\s*([A-Z0-9\-\/]+)",
            re.IGNORECASE,
        ),

        # Total Amount: RM with optional commas
        # Matches: "Total: RM 1,500.50", "Jumlah: RM150"
        "total_amount": re.compile(
            r"(?:total|jumlah|amount|grand\s*total|bill\s*total):?\s*RM\s*([\d,]+\.?\d{0,2})",
            re.IGNORECASE,
        ),

        # GST/SST Amount
        # Handles both GST (pre-2018) and SST (current)
        "gst_sst_amount": re.compile(
            r"(?:gst|sst|tax|cukai):?\s*(?:\(\d+%\))?\s*RM\s*([\d,]+\.?\d{0,2})",
            re.IGNORECASE,
        ),

        # Provider Address (optional field)
        # Looks for address patterns ending with Malaysian states/cities
        "provider_address": re.compile(
            r"(?:address|alamat):?\s*([A-Za-z0-9\s,\.\-]+(?:Malaysia|Kuala Lumpur|KL|Selangor|Penang|Johor|Melaka|Pahang|Perak))",
            re.IGNORECASE,
        ),
    }

    # Fallback patterns for when primary patterns fail
    AMOUNT_FALLBACK = re.compile(
        r"(?:total|jumlah|amount):?\s*([\d,]+\.?\d{2})", re.IGNORECASE
    )
    DATE_FALLBACK = re.compile(r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})")

    @classmethod
    async def extract_from_body(
        cls, body_text: str
    ) -> dict[str, EmailFieldExtraction]:
        """
        Extract claim fields from email body text.

        Args:
            body_text: Normalized email body text (plain text, no HTML)

        Returns:
            Dict mapping field_name to EmailFieldExtraction with confidence scores.
            All fields are included, even if not found (confidence=0.0).

        Example:
            >>> body = "Member: John\\nDate: 15/12/2024\\nTotal: RM 150"
            >>> result = await BodyTextParser.extract_from_body(body)
            >>> result['member_name'].value
            'John'
            >>> result['total_amount'].confidence
            0.9
        """
        if not body_text or not body_text.strip():
            logger.warning("Empty body text provided to BodyTextParser")
            return cls._empty_extractions()

        logger.info("extracting_fields_from_body", text_length=len(body_text))

        results = {}

        # Extract each field using patterns
        for field_name, pattern in cls.PATTERNS.items():
            extraction = cls._extract_field(field_name, pattern, body_text)
            if extraction.value:
                results[field_name] = extraction
                logger.debug(
                    "field_extracted",
                    field=field_name,
                    value=extraction.value,
                    confidence=extraction.confidence,
                )

        # Apply fallback patterns if primary patterns failed
        if "total_amount" not in results:
            extraction = cls._extract_field(
                "total_amount", cls.AMOUNT_FALLBACK, body_text
            )
            if extraction.value:
                results["total_amount"] = extraction
                logger.debug("fallback_amount_extracted", value=extraction.value)

        if "service_date" not in results:
            extraction = cls._extract_field(
                "service_date", cls.DATE_FALLBACK, body_text
            )
            if extraction.value:
                results["service_date"] = extraction
                logger.debug("fallback_date_extracted", value=extraction.value)

        logger.info("extraction_complete", fields_found=len(results))
        return results

    @classmethod
    def _extract_field(
        cls, field_name: str, pattern: re.Pattern, text: str
    ) -> EmailFieldExtraction:
        """
        Extract a single field using regex pattern.

        Args:
            field_name: Name of field being extracted
            pattern: Compiled regex pattern
            text: Text to search

        Returns:
            EmailFieldExtraction with value and confidence
        """
        match = pattern.search(text)
        if not match:
            return EmailFieldExtraction(
                field_name=field_name,
                value=None,
                confidence=0.0,
                extraction_method="regex"
            )

        raw_value = match.group(1).strip()

        # Post-process based on field type
        if field_name == "service_date":
            parsed_date = cls._parse_malaysian_date(raw_value)
            if parsed_date:
                value = parsed_date.isoformat()
                confidence = 0.85  # High confidence if date parses
            else:
                return EmailFieldExtraction(
                    field_name=field_name,
                    value=None,
                    confidence=0.0,
                    extraction_method="regex"
                )

        elif field_name in ["total_amount", "gst_sst_amount"]:
            parsed_amount = cls._parse_malaysian_currency(raw_value)
            if parsed_amount is not None:
                value = str(parsed_amount)
                confidence = 0.9  # High confidence for numeric extraction
            else:
                return EmailFieldExtraction(
                    field_name=field_name,
                    value=None,
                    confidence=0.0,
                    extraction_method="regex"
                )

        else:
            value = raw_value
            # Confidence based on pattern specificity
            if field_name in ["member_id", "receipt_number"]:
                confidence = 0.85  # Structured IDs have high confidence
            elif field_name == "member_name":
                confidence = 0.8  # Names can vary
            elif field_name == "provider_name":
                confidence = 0.8  # Provider names are usually reliable
            else:
                confidence = 0.75  # Default confidence

        return EmailFieldExtraction(
            field_name=field_name,
            value=value,
            confidence=confidence,
            extraction_method="regex"
        )

    @staticmethod
    def _parse_malaysian_date(date_str: str) -> Optional[datetime]:
        """
        Parse Malaysian date format (DD/MM/YYYY, DD-MM-YYYY).

        Handles:
        - DD/MM/YYYY
        - DD-MM-YYYY
        - DD.MM.YYYY
        - Both 2-digit and 4-digit years

        Args:
            date_str: Date string to parse

        Returns:
            datetime object or None if parsing fails

        Example:
            >>> BodyTextParser._parse_malaysian_date("15/12/2024")
            datetime(2024, 12, 15, 0, 0)
            >>> BodyTextParser._parse_malaysian_date("01-06-24")
            datetime(2024, 6, 1, 0, 0)
        """
        try:
            # Use dateutil parser with dayfirst=True for Malaysian format
            parsed = date_parser.parse(date_str, dayfirst=True)

            # Validate date is reasonable (not in future, not before 1900)
            now = datetime.now()
            if parsed > now:
                logger.warning("date_in_future", date_str=date_str)
                return None
            if parsed.year < 1900:
                logger.warning("date_too_old", date_str=date_str, year=parsed.year)
                return None

            return parsed
        except (ValueError, TypeError) as e:
            logger.warning("date_parse_failed", date_str=date_str, error=str(e))
            return None

    @staticmethod
    def _parse_malaysian_currency(amount_str: str) -> Optional[float]:
        """
        Parse Malaysian Ringgit currency format.

        Handles:
        - RM 1,500.50 -> 1500.50
        - RM 150 -> 150.00
        - 1,500.50 -> 1500.50

        Args:
            amount_str: Currency string to parse

        Returns:
            Float amount or None if parsing fails

        Example:
            >>> BodyTextParser._parse_malaysian_currency("RM 1,500.50")
            1500.5
            >>> BodyTextParser._parse_malaysian_currency("150.00")
            150.0
        """
        try:
            # Remove RM prefix if present
            clean = amount_str.replace("RM", "").strip()

            # Remove commas
            clean = clean.replace(",", "")

            # Convert to float
            amount = float(clean)

            # Validate reasonable amount
            if amount <= 0:
                logger.warning("invalid_amount_zero_or_negative", amount=amount)
                return None
            if amount > 1_000_000:  # Unlikely claim > RM 1M
                logger.warning("amount_exceeds_threshold", amount=amount)
                # Don't reject, but log warning

            return amount
        except (ValueError, TypeError) as e:
            logger.warning("amount_parse_failed", amount_str=amount_str, error=str(e))
            return None

    @classmethod
    def _empty_extractions(cls) -> dict[str, EmailFieldExtraction]:
        """
        Return empty extractions for all fields.

        Returns:
            Dictionary with all fields having None values and 0.0 confidence
        """
        return {
            field_name: EmailFieldExtraction(
                field_name=field_name,
                value=None,
                confidence=0.0,
                extraction_method="regex"
            )
            for field_name in cls.PATTERNS.keys()
        }
