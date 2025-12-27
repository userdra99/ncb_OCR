"""Email metadata models."""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, EmailStr


class EmailMetadata(BaseModel):
    """Email metadata from Gmail."""

    message_id: str
    sender: str  # Email address
    subject: str
    received_at: datetime
    attachments: list[str]  # List of attachment filenames
    labels: list[str] = []
    body_text: str = ""
    parsed_fields: Optional[Any] = None  # EmailExtractionResult - using Any to avoid circular import

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class EmailAttachment(BaseModel):
    """Email attachment details."""

    attachment_id: str
    filename: str
    mime_type: str
    size_bytes: int
