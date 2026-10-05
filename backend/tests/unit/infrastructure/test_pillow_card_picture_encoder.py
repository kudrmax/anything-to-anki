"""Every card picture — video frame or picked picture — is shrunk the same way."""
from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.adapters.pillow_card_picture_encoder import (
    CARD_PICTURE_MAX_WIDTH,
    PillowCardPictureEncoder,
)
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


def _picture(width: int, height: int, mode: str = "RGB", fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (width, height), color="red").save(buffer, format=fmt)
    return buffer.getvalue()


class TestPillowCardPictureEncoder:
    def test_writes_webp(self, tmp_path: Path) -> None:
        out = tmp_path / "card.webp"

        PillowCardPictureEncoder().encode(_picture(100, 50, fmt="JPEG"), str(out))

        with Image.open(out) as img:
            assert img.format == "WEBP"

    def test_shrinks_a_wide_picture_to_card_width_keeping_proportions(
        self, tmp_path: Path,
    ) -> None:
        out = tmp_path / "card.webp"

        PillowCardPictureEncoder().encode(_picture(CARD_PICTURE_MAX_WIDTH * 2, 600), str(out))

        with Image.open(out) as img:
            assert img.size == (CARD_PICTURE_MAX_WIDTH, 300)

    def test_never_enlarges_a_small_picture(self, tmp_path: Path) -> None:
        out = tmp_path / "card.webp"

        PillowCardPictureEncoder().encode(_picture(200, 100), str(out))

        with Image.open(out) as img:
            assert img.size == (200, 100)

    def test_drops_transparency(self, tmp_path: Path) -> None:
        out = tmp_path / "card.webp"

        PillowCardPictureEncoder().encode(_picture(50, 50, mode="RGBA"), str(out))

        with Image.open(out) as img:
            assert img.mode == "RGB"

    def test_leaves_no_file_when_bytes_are_not_a_picture(self, tmp_path: Path) -> None:
        out = tmp_path / "card.webp"

        with pytest.raises(OSError):
            PillowCardPictureEncoder().encode(b"<html>not a picture</html>", str(out))

        assert list(tmp_path.iterdir()) == []
