"""
Tests for email text extraction utilities.
"""

import pytest
from src.utils.email_text_extractor import (
    HTMLTextExtractor,
    TextNormalizer,
    EmailTextExtractor,
    extract_email_text
)


class TestHTMLTextExtractor:
    """Tests for HTMLTextExtractor class."""

    def test_simple_html(self):
        """Test extraction from simple HTML."""
        extractor = HTMLTextExtractor()
        extractor.feed('<p>Hello World</p>')
        assert extractor.get_text() == 'Hello World'

    def test_nested_tags(self):
        """Test extraction from nested HTML tags."""
        extractor = HTMLTextExtractor()
        extractor.feed('<p>Hello <strong>bold</strong> and <em>italic</em></p>')
        text = extractor.get_text()
        assert 'Hello' in text
        assert 'bold' in text
        assert 'italic' in text

    def test_block_tags_add_newlines(self):
        """Test that block tags add newlines."""
        extractor = HTMLTextExtractor()
        extractor.feed('<p>Paragraph 1</p><p>Paragraph 2</p>')
        text = extractor.get_text()
        assert 'Paragraph 1' in text
        assert 'Paragraph 2' in text
        # Should have some separation
        assert text.count('\n') > 0

    def test_script_tags_ignored(self):
        """Test that script and style tags are ignored."""
        extractor = HTMLTextExtractor()
        extractor.feed(
            '<p>Visible</p>'
            '<script>alert("hidden")</script>'
            '<style>body { color: red; }</style>'
        )
        text = extractor.get_text()
        assert 'Visible' in text
        assert 'alert' not in text
        assert 'color' not in text

    def test_empty_html(self):
        """Test extraction from empty HTML."""
        extractor = HTMLTextExtractor()
        extractor.feed('<div></div>')
        assert extractor.get_text() == ''

    def test_complex_html_email(self):
        """Test extraction from complex HTML email."""
        html = """
        <html>
            <head><title>Email</title></head>
            <body>
                <div>
                    <h1>Claim Submission</h1>
                    <p>Member ID: <strong>12345</strong></p>
                    <p>Amount: RM 100.00</p>
                    <br>
                    <p>Please find attached receipt.</p>
                </div>
            </body>
        </html>
        """
        extractor = HTMLTextExtractor()
        extractor.feed(html)
        text = extractor.get_text()

        assert 'Claim Submission' in text
        assert '12345' in text
        assert 'RM 100.00' in text
        assert 'Please find attached receipt' in text
        assert '<html>' not in text
        assert '<body>' not in text


class TestTextNormalizer:
    """Tests for TextNormalizer class."""

    def test_basic_normalization(self):
        """Test basic whitespace normalization."""
        normalizer = TextNormalizer()
        text = '  Hello   World  '
        assert normalizer.normalize(text) == 'Hello World'

    def test_multiple_newlines(self):
        """Test normalization of multiple newlines."""
        normalizer = TextNormalizer()
        text = 'Line 1\n\n\n\nLine 2'
        result = normalizer.normalize(text)
        assert 'Line 1' in result
        assert 'Line 2' in result
        # Should reduce to max 2 newlines
        assert '\n\n\n' not in result

    def test_signature_removal_standard(self):
        """Test removal of standard email signature."""
        normalizer = TextNormalizer()
        text = """
        This is the main content.

        --
        John Doe
        Company Name
        """
        result = normalizer.normalize(text)
        assert 'main content' in result
        assert 'John Doe' not in result
        assert 'Company Name' not in result

    def test_signature_removal_mobile(self):
        """Test removal of mobile signatures."""
        normalizer = TextNormalizer()

        # iPhone signature
        text1 = "Message content\n\nSent from my iPhone"
        assert 'Sent from' not in normalizer.normalize(text1)

        # Android signature
        text2 = "Message content\n\nSent from Android"
        assert 'Sent from' not in normalizer.normalize(text2)

    def test_unicode_normalization(self):
        """Test Unicode normalization."""
        normalizer = TextNormalizer()
        # NFKC normalization should handle compatibility characters
        text = 'Café'  # May have different Unicode representations
        result = normalizer.normalize(text)
        assert 'Caf' in result

    def test_tab_to_space(self):
        """Test tab conversion to spaces."""
        normalizer = TextNormalizer()
        text = 'Column1\tColumn2\tColumn3'
        result = normalizer.normalize(text)
        assert '\t' not in result
        assert 'Column1' in result
        assert 'Column2' in result

    def test_empty_text(self):
        """Test normalization of empty text."""
        normalizer = TextNormalizer()
        assert normalizer.normalize('') == ''
        assert normalizer.normalize('   ') == ''


class TestEmailTextExtractor:
    """Tests for EmailTextExtractor class."""

    def test_extract_plain_text(self):
        """Test extraction of plain text."""
        extractor = EmailTextExtractor()
        text = 'Hello, this is a plain text email.'
        result = extractor.extract_text(text, 'text/plain')
        assert result == text

    def test_extract_html_text(self):
        """Test extraction of HTML text."""
        extractor = EmailTextExtractor()
        html = '<p>Hello, this is an <strong>HTML</strong> email.</p>'
        result = extractor.extract_text(html, 'text/html')
        assert 'Hello' in result
        assert 'HTML' in result
        assert '<p>' not in result
        assert '<strong>' not in result

    def test_empty_body(self):
        """Test extraction from empty body."""
        extractor = EmailTextExtractor()
        assert extractor.extract_text('', 'text/plain') == ''
        assert extractor.extract_text('', 'text/html') == ''

    def test_malformed_html(self):
        """Test handling of malformed HTML."""
        extractor = EmailTextExtractor()
        html = '<p>Unclosed paragraph<div>Nested</p></div>'
        result = extractor.extract_text(html, 'text/html')
        # Should not crash, should extract text
        assert 'Unclosed' in result or 'Nested' in result

    def test_multipart_prefer_plain(self):
        """Test multipart extraction prefers plain text."""
        extractor = EmailTextExtractor()
        parts = [
            ('text/plain', 'Plain version'),
            ('text/html', '<p>HTML version</p>')
        ]
        result = extractor.extract_from_multipart(parts)
        assert result == 'Plain version'

    def test_multipart_html_only(self):
        """Test multipart extraction with only HTML."""
        extractor = EmailTextExtractor()
        parts = [
            ('text/html', '<p>HTML only</p>')
        ]
        result = extractor.extract_from_multipart(parts)
        assert 'HTML only' in result
        assert '<p>' not in result

    def test_multipart_empty(self):
        """Test multipart extraction with empty parts."""
        extractor = EmailTextExtractor()
        assert extractor.extract_from_multipart([]) == ''

    def test_case_insensitive_mime_type(self):
        """Test that MIME type matching is case-insensitive."""
        extractor = EmailTextExtractor()
        html = '<p>Test</p>'

        result1 = extractor.extract_text(html, 'text/html')
        result2 = extractor.extract_text(html, 'TEXT/HTML')
        result3 = extractor.extract_text(html, 'Text/Html')

        assert result1 == result2 == result3

    def test_real_world_claim_email(self):
        """Test extraction from realistic claim email."""
        extractor = EmailTextExtractor()
        html = """
        <html>
        <body>
            <p>Dear Claims Department,</p>
            <p>Please find attached my medical claim for:</p>
            <ul>
                <li>Member ID: M123456</li>
                <li>Service Date: 15/12/2024</li>
                <li>Provider: Klinik Kesihatan</li>
                <li>Amount: RM 85.50</li>
            </ul>
            <p>Receipt is attached.</p>
            <p>Thank you.</p>
            --
            <p>John Doe<br>
            Sent from my iPhone</p>
        </body>
        </html>
        """
        result = extractor.extract_text(html, 'text/html')

        # Should extract key information
        assert 'M123456' in result
        assert '15/12/2024' in result
        assert 'RM 85.50' in result
        assert 'Klinik Kesihatan' in result

        # Should remove signature
        assert 'Sent from my iPhone' not in result

    def test_normalization_applied(self):
        """Test that normalization is applied to extracted text."""
        extractor = EmailTextExtractor()
        text = 'Line 1\n\n\n\n--\nSignature'
        result = extractor.extract_text(text, 'text/plain')

        # Signature should be removed
        assert 'Signature' not in result
        # Multiple newlines should be reduced
        assert '\n\n\n' not in result


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_extract_email_text_plain(self):
        """Test convenience function with plain text."""
        result = extract_email_text('Hello World', 'text/plain')
        assert result == 'Hello World'

    def test_extract_email_text_html(self):
        """Test convenience function with HTML."""
        result = extract_email_text('<p>Hello World</p>', 'text/html')
        assert 'Hello World' in result
        assert '<p>' not in result

    def test_extract_email_text_default_mime(self):
        """Test convenience function with default MIME type."""
        result = extract_email_text('Hello World')
        assert result == 'Hello World'


class TestErrorHandling:
    """Tests for error handling."""

    def test_extractor_never_raises(self):
        """Test that extractor never raises exceptions."""
        extractor = EmailTextExtractor()

        # Should return empty string, not raise
        assert extractor.extract_text(None, 'text/plain') == ''

        # Malformed HTML should not raise
        result = extractor.extract_text('<<<>>>', 'text/html')
        assert isinstance(result, str)

    def test_normalizer_handles_errors(self):
        """Test that normalizer handles errors gracefully."""
        normalizer = TextNormalizer()

        # Should not raise on None
        result = normalizer.normalize(None)
        assert result == ''


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
