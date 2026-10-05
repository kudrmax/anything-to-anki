from __future__ import annotations

from abc import ABC, abstractmethod


class CardPictureEncoder(ABC):
    """Port for turning any picture — a video frame or a downloaded one — into the
    compact file a card carries. Every card picture goes through it, so all of
    them share one size and one format."""

    @abstractmethod
    def encode(self, picture: bytes, out_path: str) -> None:
        """Shrink the picture to card size and write it to out_path.

        Leaves no half-written file behind. Raises OSError when the bytes are
        not a picture."""
