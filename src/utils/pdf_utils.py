"""PDF utilities for converting PDFs to images."""

from pathlib import Path
from typing import List

from pdf2image import convert_from_path
from PIL import Image

from src.utils.logging import get_logger

logger = get_logger(__name__)


def pdf_to_images(pdf_path: Path, dpi: int = 300) -> List[Path]:
    """
    Convert PDF pages to images.

    Args:
        pdf_path: Path to PDF file
        dpi: Resolution for conversion (default 300 for good OCR quality)

    Returns:
        List of image file paths
    """
    logger.info("Converting PDF to images", pdf_path=str(pdf_path), dpi=dpi)

    try:
        # Convert PDF to PIL Images
        images = convert_from_path(
            str(pdf_path),
            dpi=dpi,
            fmt='jpeg',
            thread_count=2
        )

        # Save images to temp directory
        output_dir = pdf_path.parent / f"{pdf_path.stem}_pages"
        output_dir.mkdir(parents=True, exist_ok=True)

        image_paths = []
        for i, image in enumerate(images, 1):
            output_path = output_dir / f"page_{i:03d}.jpg"
            image.save(output_path, 'JPEG', quality=95)
            image_paths.append(output_path)
            logger.debug(f"Converted page {i}/{len(images)}", output_path=str(output_path))

        logger.info(
            "PDF conversion complete",
            pdf_path=str(pdf_path),
            total_pages=len(images)
        )

        return image_paths

    except Exception as e:
        logger.error("PDF conversion failed", pdf_path=str(pdf_path), error=str(e))
        raise


def cleanup_pdf_images(image_paths: List[Path]) -> None:
    """
    Clean up temporary image files created from PDF.

    Args:
        image_paths: List of image paths to delete
    """
    for img_path in image_paths:
        try:
            if img_path.exists():
                img_path.unlink()
                logger.debug("Deleted temp image", path=str(img_path))

            # Remove directory if empty
            parent_dir = img_path.parent
            if parent_dir.exists() and not any(parent_dir.iterdir()):
                parent_dir.rmdir()
                logger.debug("Removed empty directory", path=str(parent_dir))

        except Exception as e:
            logger.warning("Failed to cleanup image", path=str(img_path), error=str(e))
