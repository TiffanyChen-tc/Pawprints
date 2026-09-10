from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


class InvalidImageError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedImage:
    bytes: bytes
    mime_type: str

    @property
    def file_size(self) -> int:
        return len(self.bytes)


FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def normalize_image(content: bytes, *, max_bytes: int, max_pixels: int) -> NormalizedImage:
    if len(content) > max_bytes:
        raise InvalidImageError("Image exceeds byte limit.")
    try:
        with Image.open(BytesIO(content)) as image:
            image_format = image.format
            if image_format not in FORMAT_TO_MIME:
                raise InvalidImageError("Unsupported image format.")
            if getattr(image, "is_animated", False) or getattr(image, "n_frames", 1) != 1:
                raise InvalidImageError("Animated images are not supported.")
            width, height = image.size
            if width * height > max_pixels:
                raise InvalidImageError("Image exceeds pixel limit.")
            image.load()
            normalized = ImageOps.exif_transpose(image)
            if image_format == "JPEG" and normalized.mode not in ("RGB", "L"):
                normalized = normalized.convert("RGB")
            output = BytesIO()
            save_format = "JPEG" if image_format == "JPEG" else image_format
            normalized.save(output, format=save_format)
            return NormalizedImage(bytes=output.getvalue(), mime_type=FORMAT_TO_MIME[image_format])
    except (OSError, UnidentifiedImageError) as exc:
        raise InvalidImageError("Invalid image.") from exc
