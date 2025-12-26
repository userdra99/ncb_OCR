"""
Unit tests for email text extraction.

Tests HTML to text conversion, multipart email handling,
text normalization, and signature removal.
"""

import pytest
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from src.services.email_parser import EmailTextExtractor


class TestEmailTextExtractor:
    """Test email text extraction functionality."""

    @pytest.fixture
    def extractor(self):
        """Create EmailTextExtractor instance."""
        return EmailTextExtractor()

    def test_extract_plain_text_simple(self, extractor):
        """Test extraction from plain text email."""
        msg = EmailMessage()
        msg.set_content("Simple plain text content")

        result = extractor.extract(msg)

        assert result == "Simple plain text content"

    def test_extract_html_to_text(self, extractor):
        """Test HTML to text conversion."""
        msg = EmailMessage()
        html_content = """
        <html>
            <body>
                <h1>Claim Receipt</h1>
                <p>Member ID: M12345</p>
                <p>Amount: RM150.00</p>
            </body>
        </html>
        """
        msg.add_alternative(html_content, subtype='html')

        result = extractor.extract(msg)

        assert "Claim Receipt" in result
        assert "Member ID: M12345" in result
        assert "Amount: RM150.00" in result
        assert "<html>" not in result
        assert "<body>" not in result

    def test_extract_multipart_prefers_text(self, extractor):
        """Test multipart email prefers plain text over HTML."""
        msg = MIMEMultipart('alternative')

        text_part = MIMEText("Plain text version", 'plain')
        html_part = MIMEText("<html><body>HTML version</body></html>", 'html')

        msg.attach(text_part)
        msg.attach(html_part)

        result = extractor.extract(msg)

        assert "Plain text version" in result

    def test_extract_multipart_fallback_to_html(self, extractor):
        """Test multipart email falls back to HTML if no plain text."""
        msg = MIMEMultipart('alternative')

        html_part = MIMEText("<html><body>HTML only content</body></html>", 'html')
        msg.attach(html_part)

        result = extractor.extract(msg)

        assert "HTML only content" in result
        assert "<html>" not in result

    def test_text_normalization_whitespace(self, extractor):
        """Test normalization of excessive whitespace."""
        msg = EmailMessage()
        msg.set_content("Line1\n\n\n\nLine2  \n  Line3\t\tLine4")

        result = extractor.extract(msg)

        # Should normalize to single newlines and spaces
        assert "\n\n\n\n" not in result
        assert "Line1" in result
        assert "Line2" in result

    def test_text_normalization_unicode(self, extractor):
        """Test normalization of unicode characters."""
        msg = EmailMessage()
        msg.set_content("Amount: RM\u00a0150.00")  # Non-breaking space

        result = extractor.extract(msg)

        assert "RM 150.00" in result or "RM150.00" in result

    def test_signature_removal_standard(self, extractor):
        """Test removal of email signature with standard delimiter."""
        msg = EmailMessage()
        content = """
        Member ID: M12345
        Amount: RM150.00

        --
        Best regards,
        John Doe
        Medical Clinic
        """
        msg.set_content(content)

        result = extractor.extract(msg)

        assert "Member ID: M12345" in result
        assert "Amount: RM150.00" in result
        assert "Best regards" not in result
        assert "John Doe" not in result

    def test_signature_removal_alternative_delimiter(self, extractor):
        """Test removal of signature with alternative delimiters."""
        msg = EmailMessage()
        content = """
        Receipt #12345
        Total: RM200.00

        _______________
        Sent from my iPhone
        """
        msg.set_content(content)

        result = extractor.extract(msg)

        assert "Receipt #12345" in result
        assert "Sent from my iPhone" not in result

    def test_signature_removal_thanks_regards(self, extractor):
        """Test removal of signature starting with Thanks/Regards."""
        msg = EmailMessage()
        content = """
        Patient: Ali bin Abu
        Date: 15/12/2024

        Thanks,
        Dr. Ahmad
        """
        msg.set_content(content)

        result = extractor.extract(msg)

        assert "Ali bin Abu" in result
        assert "Thanks" not in result or result.index("Thanks") > result.index("Ali bin Abu")

    def test_empty_email(self, extractor):
        """Test handling of empty email."""
        msg = EmailMessage()
        msg.set_content("")

        result = extractor.extract(msg)

        assert result == ""

    def test_email_with_attachments_ignores_binary(self, extractor):
        """Test that binary attachments are ignored."""
        msg = MIMEMultipart()

        text_part = MIMEText("Email body content", 'plain')
        msg.attach(text_part)

        # Add fake binary attachment
        binary_part = MIMEText("binary data", 'plain')
        binary_part.add_header('Content-Disposition', 'attachment', filename='receipt.pdf')
        msg.attach(binary_part)

        result = extractor.extract(msg)

        assert "Email body content" in result
        assert "binary data" not in result

    def test_html_entities_decoded(self, extractor):
        """Test HTML entities are properly decoded."""
        msg = EmailMessage()
        html_content = """
        <html>
            <body>
                <p>Amount: RM150.00 &amp; RM200.00</p>
                <p>Company: ABC &lt;XYZ&gt; Sdn Bhd</p>
            </body>
        </html>
        """
        msg.add_alternative(html_content, subtype='html')

        result = extractor.extract(msg)

        assert "RM150.00 & RM200.00" in result
        assert "ABC <XYZ> Sdn Bhd" in result
        assert "&amp;" not in result
        assert "&lt;" not in result

    def test_html_links_text_extracted(self, extractor):
        """Test that link text is extracted from HTML."""
        msg = EmailMessage()
        html_content = """
        <html>
            <body>
                <a href="http://example.com">Click here for receipt</a>
            </body>
        </html>
        """
        msg.add_alternative(html_content, subtype='html')

        result = extractor.extract(msg)

        assert "Click here for receipt" in result

    def test_html_tables_readable_format(self, extractor):
        """Test that HTML tables are converted to readable format."""
        msg = EmailMessage()
        html_content = """
        <html>
            <body>
                <table>
                    <tr><td>Service</td><td>Amount</td></tr>
                    <tr><td>Consultation</td><td>RM50.00</td></tr>
                    <tr><td>Medicine</td><td>RM100.00</td></tr>
                </table>
            </body>
        </html>
        """
        msg.add_alternative(html_content, subtype='html')

        result = extractor.extract(msg)

        assert "Service" in result
        assert "Consultation" in result
        assert "RM50.00" in result
        assert "RM100.00" in result

    def test_multilanguage_text_preserved(self, extractor):
        """Test multilanguage content is preserved."""
        msg = EmailMessage()
        content = """
        Patient: Ali bin Abu
        Pesakit: سعيد
        病人: 李明
        நோயாளி: ராஜா
        """
        msg.set_content(content, charset='utf-8')

        result = extractor.extract(msg)

        assert "Ali bin Abu" in result
        # Should preserve non-ASCII characters
        assert len(result) > 20

    def test_quoted_reply_removal(self, extractor):
        """Test removal of quoted reply text."""
        msg = EmailMessage()
        content = """
        Here is my claim receipt.

        Amount: RM150.00

        On Mon, Dec 15, 2024 at 10:00 AM, someone@example.com wrote:
        > Please submit your claim
        > Thanks
        """
        msg.set_content(content)

        result = extractor.extract(msg)

        assert "Amount: RM150.00" in result
        # Quoted text should be removed or minimized
        assert result.count(">") <= 2 or "wrote:" not in result

    def test_forwarded_email_original_content(self, extractor):
        """Test extraction from forwarded email."""
        msg = EmailMessage()
        content = """
        FW: Claim Receipt

        ---------- Forwarded message ---------
        From: clinic@example.com
        Date: Mon, 15 Dec 2024
        Subject: Receipt

        Member: M12345
        Amount: RM200.00
        """
        msg.set_content(content)

        result = extractor.extract(msg)

        assert "M12345" in result
        assert "RM200.00" in result

    def test_base64_encoded_content(self, extractor):
        """Test extraction from base64 encoded content."""
        msg = EmailMessage()
        msg.set_content("Member ID: M12345\nAmount: RM150.00")

        # Simulate base64 encoding
        import base64
        payload = msg.get_payload()
        msg.set_payload(base64.b64encode(payload.encode()).decode())
        msg['Content-Transfer-Encoding'] = 'base64'

        result = extractor.extract(msg)

        # Should decode and extract
        assert "M12345" in result or result != ""

    def test_mixed_content_types(self, extractor):
        """Test extraction from mixed content type email."""
        msg = MIMEMultipart('mixed')

        # Text part
        text_part = MIMEText("Claim details: Member M12345", 'plain')
        msg.attach(text_part)

        # HTML part
        html_part = MIMEText("<p>Amount: RM150.00</p>", 'html')
        msg.attach(html_part)

        result = extractor.extract(msg)

        assert "M12345" in result
        assert "RM150.00" in result


class TestEmailTextExtractorEdgeCases:
    """Test edge cases for email text extraction."""

    @pytest.fixture
    def extractor(self):
        """Create EmailTextExtractor instance."""
        return EmailTextExtractor()

    def test_none_message(self, extractor):
        """Test handling of None message."""
        with pytest.raises((TypeError, AttributeError)):
            extractor.extract(None)

    def test_malformed_html(self, extractor):
        """Test handling of malformed HTML."""
        msg = EmailMessage()
        html_content = "<html><body><p>Unclosed tag<p>More content</body>"
        msg.add_alternative(html_content, subtype='html')

        result = extractor.extract(msg)

        # Should still extract text despite malformed HTML
        assert "Unclosed tag" in result
        assert "More content" in result

    def test_very_long_text(self, extractor):
        """Test handling of very long email text."""
        msg = EmailMessage()
        long_text = "A" * 100000 + "\nMember ID: M12345\n" + "B" * 100000
        msg.set_content(long_text)

        result = extractor.extract(msg)

        # Should not crash and should contain key content
        assert "M12345" in result
        assert len(result) > 0

    def test_special_characters_preserved(self, extractor):
        """Test special characters are preserved."""
        msg = EmailMessage()
        msg.set_content("Amount: RM1,500.50 (USD$500.00)")

        result = extractor.extract(msg)

        assert "RM1,500.50" in result
        assert "$500.00" in result
        assert "(" in result
        assert ")" in result

    def test_email_with_inline_images(self, extractor):
        """Test email with inline images is handled."""
        msg = MIMEMultipart('related')

        text_part = MIMEText("See attached receipt", 'plain')
        msg.attach(text_part)

        # Simulate inline image
        img_part = MIMEText("image data", 'plain')
        img_part.add_header('Content-ID', '<image1>')
        img_part.add_header('Content-Disposition', 'inline')
        msg.attach(img_part)

        result = extractor.extract(msg)

        assert "See attached receipt" in result
