#!/usr/bin/env python3
"""
Quick sanity check for email_text_extractor module.
"""

import sys
sys.path.insert(0, '/home/dra/projects/ncb_OCR')

from src.utils.email_text_extractor import (
    HTMLTextExtractor,
    TextNormalizer,
    EmailTextExtractor,
    extract_email_text
)


def test_html_extraction():
    """Test HTML extraction."""
    print("Testing HTML extraction...")
    extractor = HTMLTextExtractor()
    extractor.feed('<p>Hello <strong>World</strong></p>')
    result = extractor.get_text()
    assert 'Hello' in result and 'World' in result
    assert '<p>' not in result
    print(f"  ✓ HTML extraction works: {repr(result)}")


def test_text_normalization():
    """Test text normalization."""
    print("\nTesting text normalization...")
    normalizer = TextNormalizer()

    # Test whitespace
    result1 = normalizer.normalize('  Hello   World  ')
    assert result1 == 'Hello World'
    print(f"  ✓ Whitespace normalization: {repr(result1)}")

    # Test signature removal
    result2 = normalizer.normalize('Content\n\n--\nSignature')
    assert 'Content' in result2
    assert 'Signature' not in result2
    print(f"  ✓ Signature removal: {repr(result2)}")


def test_email_text_extractor():
    """Test EmailTextExtractor."""
    print("\nTesting EmailTextExtractor...")
    extractor = EmailTextExtractor()

    # Plain text
    result1 = extractor.extract_text('Hello World', 'text/plain')
    assert result1 == 'Hello World'
    print(f"  ✓ Plain text: {repr(result1)}")

    # HTML
    result2 = extractor.extract_text('<p>HTML Text</p>', 'text/html')
    assert 'HTML Text' in result2
    assert '<p>' not in result2
    print(f"  ✓ HTML text: {repr(result2)}")

    # Multipart
    parts = [
        ('text/plain', 'Plain version'),
        ('text/html', '<p>HTML version</p>')
    ]
    result3 = extractor.extract_from_multipart(parts)
    assert result3 == 'Plain version'
    print(f"  ✓ Multipart (prefers plain): {repr(result3)}")


def test_convenience_function():
    """Test convenience function."""
    print("\nTesting convenience function...")
    result = extract_email_text('<p>Test</p>', 'text/html')
    assert 'Test' in result
    assert '<p>' not in result
    print(f"  ✓ Convenience function: {repr(result)}")


def test_real_world_example():
    """Test with realistic claim email."""
    print("\nTesting real-world claim email...")
    html = """
    <html>
    <body>
        <p>Medical Claim Submission</p>
        <p>Member ID: M123456</p>
        <p>Amount: RM 85.50</p>
        <p>Service Date: 15/12/2024</p>
        --
        <p>Sent from my iPhone</p>
    </body>
    </html>
    """
    result = extract_email_text(html, 'text/html')
    assert 'M123456' in result
    assert 'RM 85.50' in result
    assert '15/12/2024' in result
    assert 'Sent from my iPhone' not in result
    print(f"  ✓ Real-world extraction:")
    print(f"    {repr(result[:100])}...")


if __name__ == '__main__':
    try:
        test_html_extraction()
        test_text_normalization()
        test_email_text_extractor()
        test_convenience_function()
        test_real_world_example()

        print("\n" + "="*60)
        print("✅ ALL SANITY CHECKS PASSED")
        print("="*60)

    except AssertionError as e:
        print(f"\n❌ ASSERTION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
