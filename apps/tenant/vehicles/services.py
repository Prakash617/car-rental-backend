import logging
import os
import uuid
from typing import Any

from django.conf import settings
from PIL import Image, ImageOps
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Maximum allowed upload size (25 MB)
MAX_FILE_SIZE = 25 * 1024 * 1024
DEFAULT_MAX_DIMENSION = 1920
DEFAULT_QUALITY = 82


def compress_and_save_vehicle_image(
    uploaded_file: Any,
    tenant_schema: str = "general",
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    quality: int = DEFAULT_QUALITY,
    preferred_format: str = "WEBP",
) -> dict[str, Any]:
    """
    Validates, auto-orients, resizes, and compresses an uploaded vehicle photo.
    Saves to the tenant's media directory and returns metadata with compression metrics.
    """
    if not uploaded_file:
        raise ValidationError("No image file provided.")

    original_size = getattr(uploaded_file, "size", 0)
    original_name = getattr(uploaded_file, "name", "vehicle_photo.jpg")

    if original_size > MAX_FILE_SIZE:
        raise ValidationError(
            f"The image file size ({round(original_size / (1024 * 1024), 1)} MB) exceeds the 25 MB limit."
        )

    try:
        # Open with Pillow
        img = Image.open(uploaded_file)

        # Auto-orient based on EXIF tag (resolves rotated phone photos)
        try:
            transposed = ImageOps.exif_transpose(img)
            if transposed is not None:
                img = transposed
        except Exception as exif_err:
            logger.debug("EXIF transposition skipped: %s", exif_err)

        orig_w, orig_h = img.size

        # High-quality aspect-ratio-preserving downscale if larger than max_dimension
        if orig_w > max_dimension or orig_h > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        # Color mode normalization
        if img.mode in ("RGBA", "LA") and preferred_format.upper() != "WEBP":
            # Flatten transparency to white background if saving as non-alpha format
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode == "P":
            img = img.convert("RGBA" if "transparency" in img.info else "RGB")
        elif img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        # Prepare storage directory
        clean_schema = "".join(c for c in tenant_schema if c.isalnum() or c in ("_", "-")) or "general"
        relative_dir = os.path.join("vehicles", clean_schema)
        full_dir = os.path.join(settings.MEDIA_ROOT, relative_dir)
        os.makedirs(full_dir, exist_ok=True)

        file_id = uuid.uuid4().hex[:16]

        # Compression execution
        if preferred_format.upper() == "WEBP":
            filename = f"{file_id}.webp"
            full_path = os.path.join(full_dir, filename)
            save_format = "WEBP"
            img.save(full_path, format="WEBP", quality=quality, method=6)
        else:
            filename = f"{file_id}.jpg"
            full_path = os.path.join(full_dir, filename)
            save_format = "JPEG"
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(full_path, format="JPEG", quality=quality, optimize=True, progressive=True)

        compressed_size = os.path.getsize(full_path)
        saved_bytes = max(0, original_size - compressed_size)
        reduction_percentage = round((saved_bytes / original_size) * 100, 1) if original_size > 0 else 0.0

        media_url_base = settings.MEDIA_URL if settings.MEDIA_URL.endswith("/") else f"{settings.MEDIA_URL}/"
        relative_url = f"{media_url_base}vehicles/{clean_schema}/{filename}"

        return {
            "url": relative_url,
            "filename": filename,
            "original_name": original_name,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "saved_bytes": saved_bytes,
            "reduction_percentage": reduction_percentage,
            "width": img.width,
            "height": img.height,
            "format": save_format,
        }

    except Exception as exc:
        logger.exception("Failed to compress and save vehicle photo: %s", exc)
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(f"Unable to process image file: {str(exc)}")
