"""Validate and sanitize uploaded images."""
import hashlib
import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException, UploadFile

from app.config import MAX_IMAGE_PIXELS, MAX_UPLOAD_BYTES


async def decode_upload(upload: UploadFile) -> tuple[Image.Image, str]:
    """Read a bounded static image and return its normalized pixels and digest."""
    if upload.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(415, detail={"code": "UNSUPPORTED_IMAGE", "detail": "Upload a PNG, JPEG, or WebP image."})
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail={"code": "IMAGE_TOO_LARGE", "detail": "Image is empty or exceeds the upload size limit."})
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data))
            if getattr(image, "n_frames", 1) != 1:
                raise HTTPException(422, detail={"code": "ANIMATED_IMAGE", "detail": "Animated images are not accepted."})
            image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, detail={"code": "INVALID_IMAGE", "detail": "The uploaded file is not a valid static image."}) from None
    if image.width * image.height > MAX_IMAGE_PIXELS:
        raise HTTPException(413, detail={"code": "IMAGE_TOO_LARGE", "detail": "Image exceeds the decoded pixel limit."})
    # Apply camera orientation and composite transparency before hashing or scoring.
    sanitized = ImageOps.exif_transpose(image).convert("RGBA")
    white = Image.new("RGBA", sanitized.size, "white")
    white.alpha_composite(sanitized)
    canonical = white.convert("RGB")
    digest = hashlib.sha256(
        canonical.width.to_bytes(4, "big") + canonical.height.to_bytes(4, "big") + canonical.tobytes()
    ).hexdigest()
    return canonical, digest
