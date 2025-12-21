"""File deduplication utilities using hash-based detection."""

import hashlib
from pathlib import Path


def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """
    Compute cryptographic hash of file.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (sha256, md5, etc.)

    Returns:
        Hex digest of file hash
    """
    hasher = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        # Read in 64KB chunks to handle large files
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return f"{algorithm}:{hasher.hexdigest()}"


def compute_content_hash(content: bytes, algorithm: str = "sha256") -> str:
    """
    Compute cryptographic hash of byte content.

    Args:
        content: Byte content
        algorithm: Hash algorithm

    Returns:
        Hex digest of content hash
    """
    hasher = hashlib.new(algorithm)
    hasher.update(content)
    return f"{algorithm}:{hasher.hexdigest()}"
