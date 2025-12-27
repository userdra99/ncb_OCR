"""Data models for Claims Data Entry Agent."""

# Import models in correct order to resolve forward references
from .extraction import EmailExtractionResult, OCRExtractionResult
from .email import EmailMetadata, EmailAttachment
from .claim import ClaimData
from .job import Job, JobStatus

# Rebuild models with forward references after all imports
EmailMetadata.model_rebuild()

__all__ = [
    "EmailExtractionResult",
    "OCRExtractionResult",
    "EmailMetadata",
    "EmailAttachment",
    "ClaimData",
    "Job",
    "JobStatus",
]
