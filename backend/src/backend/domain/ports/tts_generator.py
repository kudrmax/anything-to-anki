from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class TTSGenerator(ABC):
    """Port for text-to-speech audio generation."""

    @abstractmethod
    def generate_audio(
        self, text: str, out_path: Path, voice: str, speed: float,
    ) -> None:
        """Generate speech audio for the given text and save to out_path."""
        ...

    @abstractmethod
    def unload(self) -> None:
        """Release model from memory."""
        ...
