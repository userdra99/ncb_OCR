"""
Email text extraction utilities.

This module provides utilities for extracting and normalizing text from email bodies,
handling both plain text and HTML formats.
"""

from html.parser import HTMLParser
from typing import Optional
import re
import unicodedata
import structlog

logger = structlog.get_logger(__name__)


class HTMLTextExtractor(HTMLParser):
    """
    Extract plain text from HTML email bodies.

    This parser strips HTML tags while preserving readable content.
    Block-level tags like <p>, <div>, <br> are converted to newlines.

    Example:
        >>> extractor = HTMLTextExtractor()
        >>> extractor.feed('<p>Hello <strong>World</strong></p>')
        >>> extractor.get_text()
        'Hello World\\n'
    """

    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []
        self.block_tags = {
            'p', 'div', 'br', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'li', 'blockquote', 'pre', 'hr', 'table'
        }
        self.skip_tags = {'script', 'style', 'head', 'meta', 'link'}
        self.current_tag: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        """
        Handle opening HTML tags.

        Args:
            tag: HTML tag name
            attrs: List of (attribute, value) tuples
        """
        self.current_tag = tag.lower()

        # Add newline for block-level tags
        if tag.lower() in self.block_tags:
            if self.text_parts and self.text_parts[-1] != '\n':
                self.text_parts.append('\n')

    def handle_endtag(self, tag: str) -> None:
        """
        Handle closing HTML tags.

        Args:
            tag: HTML tag name
        """
        # Add newline after block-level tags
        if tag.lower() in self.block_tags:
            if self.text_parts and self.text_parts[-1] != '\n':
                self.text_parts.append('\n')

        self.current_tag = None

    def handle_data(self, data: str) -> None:
        """
        Handle text data within HTML tags.

        Args:
            data: Text content
        """
        # Skip content from script/style tags
        if self.current_tag in self.skip_tags:
            return

        # Add non-empty text
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)
            # Add space after inline content
            if self.current_tag not in self.block_tags:
                self.text_parts.append(' ')

    def get_text(self) -> str:
        """
        Get the extracted plain text.

        Returns:
            Extracted and cleaned plain text
        """
        text = ''.join(self.text_parts)
        # Clean up multiple spaces and newlines
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        return text.strip()


class TextNormalizer:
    """
    Normalize email text for extraction.

    Handles Unicode normalization, whitespace cleanup, and email signature removal.

    Example:
        >>> normalizer = TextNormalizer()
        >>> normalizer.normalize('Hello\\n\\n--\\nJohn Doe\\nSent from iPhone')
        'Hello'
    """

    # Common email signature patterns
    SIGNATURE_PATTERNS = [
        r'\n\s*--\s*\n.*$',  # Standard -- delimiter (with optional whitespace)
        r'\n_{3,}\s*\n.*$',  # Underscore delimiter
        r'\nSent from (my )?(iPhone|Android|iPad|BlackBerry).*$',
        r'\nGet Outlook for (iOS|Android).*$',
        r'\n\*{3,}.*$',  # Asterisk delimiter
        r'\nBest regards,?\s*\n.*$',
        r'\nSincerely,?\s*\n.*$',
        r'\nThanks,?\s*\n.*$',
        r'\nRegards,?\s*\n.*$',
    ]

    def __init__(self):
        self.signature_regex = re.compile(
            '|'.join(self.SIGNATURE_PATTERNS),
            re.IGNORECASE | re.DOTALL
        )

    def normalize(self, text: str) -> str:
        """
        Normalize text content.

        Performs the following operations:
        1. Unicode normalization (NFKC)
        2. Remove email signatures
        3. Clean whitespace
        4. Remove excessive newlines

        Args:
            text: Raw text to normalize

        Returns:
            Normalized text

        Example:
            >>> normalizer = TextNormalizer()
            >>> normalizer.normalize('  Hello\\n\\n\\n  World  ')
            'Hello\\n\\nWorld'
        """
        if not text:
            return ''

        try:
            # Unicode normalization (NFKC: compatibility composition)
            text = unicodedata.normalize('NFKC', text)

            # Remove email signatures
            text = self.signature_regex.sub('', text)

            # Clean whitespace
            # Replace tabs with spaces
            text = text.replace('\t', ' ')

            # Replace multiple spaces with single space
            text = re.sub(r' +', ' ', text)

            # Replace multiple newlines with max 2
            text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

            # Remove leading/trailing whitespace from each line
            lines = [line.strip() for line in text.split('\n')]
            text = '\n'.join(lines)

            # Final trim
            text = text.strip()

            return text

        except Exception as e:
            logger.warning(
                "text_normalization_failed",
                error=str(e),
                text_length=len(text)
            )
            return text.strip()


class EmailTextExtractor:
    """
    Extract and normalize text from email bodies.

    Handles multiple MIME types and provides clean, normalized text output
    suitable for further processing.

    Example:
        >>> extractor = EmailTextExtractor()
        >>> text = extractor.extract_text(
        ...     '<html><body><p>Claim info</p></body></html>',
        ...     mime_type='text/html'
        ... )
        >>> 'Claim info' in text
        True
    """

    def __init__(self):
        self.html_extractor_class = HTMLTextExtractor
        self.normalizer = TextNormalizer()

    def extract_text(
        self,
        email_body: str,
        mime_type: str = 'text/plain'
    ) -> str:
        """
        Extract text from email body.

        Automatically detects and handles different MIME types:
        - text/plain: Direct normalization
        - text/html: HTML parsing and text extraction
        - multipart/*: Falls back to plain text handling

        Args:
            email_body: Raw email body content
            mime_type: MIME type (e.g., 'text/plain', 'text/html')

        Returns:
            Normalized plain text. Returns empty string on error.

        Example:
            >>> extractor = EmailTextExtractor()
            >>> extractor.extract_text('Hello World', 'text/plain')
            'Hello World'
        """
        if not email_body:
            logger.debug("extract_text_empty_body", mime_type=mime_type)
            return ''

        try:
            # Determine extraction method based on MIME type
            mime_lower = mime_type.lower()

            if 'html' in mime_lower:
                text = self._extract_from_html(email_body)
            else:
                # Treat as plain text (handles text/plain, multipart/*, etc.)
                text = email_body

            # Normalize the extracted text
            normalized = self.normalizer.normalize(text)

            logger.debug(
                "text_extracted",
                mime_type=mime_type,
                original_length=len(email_body),
                extracted_length=len(normalized)
            )

            return normalized

        except Exception as e:
            logger.error(
                "text_extraction_failed",
                error=str(e),
                mime_type=mime_type,
                body_length=len(email_body)
            )
            # Return empty string on error, never raise
            return ''

    def _extract_from_html(self, html_content: str) -> str:
        """
        Extract plain text from HTML content.

        Args:
            html_content: HTML string

        Returns:
            Plain text extracted from HTML
        """
        try:
            parser = self.html_extractor_class()
            parser.feed(html_content)
            return parser.get_text()
        except Exception as e:
            logger.warning(
                "html_parsing_failed",
                error=str(e),
                falling_back_to_plain=True
            )
            # Fallback: strip tags with regex (less robust but better than nothing)
            text = re.sub(r'<[^>]+>', ' ', html_content)
            return text

    def extract_from_multipart(
        self,
        parts: list[tuple[str, str]]
    ) -> str:
        """
        Extract text from multipart email.

        Prefers text/plain over text/html. If both exist, uses plain text.

        Args:
            parts: List of (mime_type, content) tuples

        Returns:
            Extracted and normalized text

        Example:
            >>> extractor = EmailTextExtractor()
            >>> parts = [
            ...     ('text/plain', 'Plain version'),
            ...     ('text/html', '<p>HTML version</p>')
            ... ]
            >>> extractor.extract_from_multipart(parts)
            'Plain version'
        """
        if not parts:
            return ''

        # Separate text/plain and text/html parts
        plain_parts = []
        html_parts = []

        for mime_type, content in parts:
            mime_lower = mime_type.lower()
            if 'text/plain' in mime_lower:
                plain_parts.append(content)
            elif 'text/html' in mime_lower:
                html_parts.append(content)

        # Prefer plain text
        if plain_parts:
            combined = '\n\n'.join(plain_parts)
            return self.extract_text(combined, 'text/plain')
        elif html_parts:
            combined = '\n\n'.join(html_parts)
            return self.extract_text(combined, 'text/html')
        else:
            logger.debug("no_text_parts_found", parts_count=len(parts))
            return ''


# Convenience function for simple use cases
def extract_email_text(
    email_body: str,
    mime_type: str = 'text/plain'
) -> str:
    """
    Convenience function to extract text from email body.

    Args:
        email_body: Raw email body content
        mime_type: MIME type (default: 'text/plain')

    Returns:
        Normalized plain text

    Example:
        >>> extract_email_text('<p>Hello</p>', 'text/html')
        'Hello'
    """
    extractor = EmailTextExtractor()
    return extractor.extract_text(email_body, mime_type)
