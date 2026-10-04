from __future__ import annotations

from enum import Enum


class ImageProvider(Enum):
    """Where a picture offered for a target comes from."""

    WIKTIONARY = "wiktionary"
    BING = "bing"
