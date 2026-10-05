from __future__ import annotations

import io
import os

from PIL import Image

from backend.domain.ports.card_picture_encoder import CardPictureEncoder

CARD_PICTURE_MAX_WIDTH = 640
CARD_PICTURE_WEBP_QUALITY = 75
_WEBP_FORMAT = "WEBP"
# Pictures with alpha decode to RGBA, which WebP would keep.
_WEBP_COLOR_MODE = "RGB"
_INCOMPLETE_SUFFIX = ".part"


class PillowCardPictureEncoder(CardPictureEncoder):
    """Scales a picture down to the card width and writes it as WebP.

    The path is stored in the DB, so a truncated file would look like a valid
    picture forever after — the file appears only once fully written.
    """

    def encode(self, picture: bytes, out_path: str) -> None:
        incomplete_path = f"{out_path}{_INCOMPLETE_SUFFIX}"
        try:
            with Image.open(io.BytesIO(picture)) as img:
                _fit_card_width(img.convert(_WEBP_COLOR_MODE)).save(
                    incomplete_path,
                    format=_WEBP_FORMAT,
                    quality=CARD_PICTURE_WEBP_QUALITY,
                )
            os.replace(incomplete_path, out_path)
        except Exception:
            if os.path.exists(incomplete_path):
                os.remove(incomplete_path)
            raise


def _fit_card_width(img: Image.Image) -> Image.Image:
    if img.width <= CARD_PICTURE_MAX_WIDTH:
        return img
    height = max(1, round(img.height * CARD_PICTURE_MAX_WIDTH / img.width))
    return img.resize((CARD_PICTURE_MAX_WIDTH, height), Image.Resampling.LANCZOS)
