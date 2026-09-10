from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.image_processing import InvalidImageError, normalize_image


def make_image(fmt: str, exif: bytes | None = None, size: tuple[int, int] = (12, 12)) -> bytes:
    image = Image.new("RGB", size, color=(10, 20, 30))
    output = BytesIO()
    kwargs = {"format": fmt}
    if exif is not None:
        kwargs["exif"] = exif
    image.save(output, **kwargs)
    return output.getvalue()


def test_jpeg_png_webp_are_decoded_and_reencoded_without_exif():
    exif = Image.Exif()
    exif[271] = "Camera Brand"
    jpeg = make_image("JPEG", exif=exif.tobytes())
    png = make_image("PNG")
    webp = make_image("WEBP")

    jpeg_result = normalize_image(jpeg, max_bytes=5_242_880, max_pixels=30_000_000)
    png_result = normalize_image(png, max_bytes=5_242_880, max_pixels=30_000_000)
    webp_result = normalize_image(webp, max_bytes=5_242_880, max_pixels=30_000_000)

    assert jpeg_result.mime_type == "image/jpeg"
    assert png_result.mime_type == "image/png"
    assert webp_result.mime_type == "image/webp"
    assert Image.open(BytesIO(jpeg_result.bytes)).getexif() == {}


def test_corrupt_file_is_rejected():
    with pytest.raises(InvalidImageError):
        normalize_image(b"not an image", max_bytes=5_242_880, max_pixels=30_000_000)


def test_animated_webp_is_rejected():
    first = Image.new("RGB", (4, 4), color=(255, 0, 0))
    second = Image.new("RGB", (4, 4), color=(0, 255, 0))
    output = BytesIO()
    first.save(output, format="WEBP", save_all=True, append_images=[second], duration=100, loop=0)

    with pytest.raises(InvalidImageError):
        normalize_image(output.getvalue(), max_bytes=5_242_880, max_pixels=30_000_000)


def test_byte_and_pixel_limits_are_rejected():
    with pytest.raises(InvalidImageError):
        normalize_image(make_image("PNG"), max_bytes=5, max_pixels=30_000_000)
    with pytest.raises(InvalidImageError):
        normalize_image(make_image("PNG", size=(20, 20)), max_bytes=5_242_880, max_pixels=100)


def test_pixel_limit_is_checked_before_full_decode(monkeypatch):
    oversized = make_image("PNG", size=(20, 20))

    def fail_load(self, *args, **kwargs):
        raise AssertionError("oversized image should not be fully decoded")

    monkeypatch.setattr(Image.Image, "load", fail_load)

    with pytest.raises(InvalidImageError, match="pixel limit"):
        normalize_image(oversized, max_bytes=5_242_880, max_pixels=100)
