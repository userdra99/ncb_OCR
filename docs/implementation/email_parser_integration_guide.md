# Email Parser Integration Guide

## Overview
How to integrate `EmailTextExtractor` into `email_parser.py` for enhanced body text extraction.

## Quick Integration

### Step 1: Import the Extractor
```python
from src.utils.email_text_extractor import EmailTextExtractor
```

### Step 2: Initialize in EmailParser
```python
class EmailParser:
    def __init__(self):
        # Existing initialization...
        self.text_extractor = EmailTextExtractor()
```

### Step 3: Use in Body Extraction
```python
def _extract_body_text(self, message: Message) -> str:
    """Extract and normalize body text from email."""

    # Get body parts
    body_parts = self._get_body_parts(message)

    if not body_parts:
        return ""

    # Check if multipart
    if len(body_parts) > 1:
        return self.text_extractor.extract_from_multipart(body_parts)

    # Single part
    mime_type, content = body_parts[0]
    return self.text_extractor.extract_text(content, mime_type)

def _get_body_parts(self, message: Message) -> list[tuple[str, str]]:
    """Extract body parts from email message."""
    parts = []

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type in ['text/plain', 'text/html']:
                try:
                    content = part.get_payload(decode=True)
                    if content:
                        charset = part.get_content_charset() or 'utf-8'
                        text = content.decode(charset, errors='replace')
                        parts.append((content_type, text))
                except Exception:
                    continue
    else:
        content_type = message.get_content_type()
        if content_type in ['text/plain', 'text/html']:
            try:
                content = message.get_payload(decode=True)
                if content:
                    charset = message.get_content_charset() or 'utf-8'
                    text = content.decode(charset, errors='replace')
                    parts.append((content_type, text))
            except Exception:
                pass

    return parts
```

## Benefits

### Before Integration
- Raw HTML in body text
- Email signatures included
- Inconsistent whitespace
- Unicode issues
- Cluttered extraction context

### After Integration
- Clean plain text
- Signatures removed
- Normalized whitespace
- Proper Unicode handling
- Focused extraction context

## Example Output Comparison

### Before
```
<html><body><p>Member ID: M123456</p><p>Amount: RM 100</p></body></html>

--
John Doe
Sent from my iPhone
```

### After
```
Member ID: M123456
Amount: RM 100
```

## Testing Integration

```python
# tests/test_email_parser_integration.py
import pytest
from src.services.email_parser import EmailParser

def test_email_body_extraction_with_text_extractor():
    parser = EmailParser()

    # Create test email with HTML body
    email_data = {
        'body': '<p>Member ID: M123456</p><p>Amount: RM 100</p>',
        'mime_type': 'text/html'
    }

    result = parser.parse_email(email_data)

    # Should extract clean text
    assert 'M123456' in result.body
    assert 'RM 100' in result.body
    assert '<p>' not in result.body
```

## Rollout Plan

1. **Phase 1**: Add extractor to email_parser.py (non-breaking)
2. **Phase 2**: Test with historical emails
3. **Phase 3**: Monitor extraction quality
4. **Phase 4**: Enable for production

## Monitoring

Track these metrics after integration:
- Body text length (should decrease)
- Extraction confidence (should increase)
- Parse errors (should stay same or decrease)
- OCR accuracy (should increase with cleaner context)

## Rollback

If issues occur, remove the extractor:
```python
# Simple rollback - just remove text_extractor usage
# Return to original body extraction logic
```

The integration is designed to be low-risk and easy to rollback.
