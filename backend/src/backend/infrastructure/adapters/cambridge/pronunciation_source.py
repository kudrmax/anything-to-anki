from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from backend.domain.ports.pronunciation_source import PronunciationSource
from backend.infrastructure.adapters.cambridge.parser import parse_cambridge_jsonl

if TYPE_CHECKING:
    from backend.infrastructure.adapters.cambridge.models import CambridgeWord


class CambridgePronunciationSource(PronunciationSource):
    """Looks up pronunciation audio URLs from Cambridge dictionary JSONL."""

    def __init__(self, cambridge_path: str | Path) -> None:
        self._data: dict[str, CambridgeWord] = parse_cambridge_jsonl(Path(cambridge_path))

    def get_audio_urls(self, lemma: str) -> tuple[str | None, str | None]:
        word = self._data.get(lemma.lower())
        if word is None:
            return None, None

        us_url: str | None = None
        uk_url: str | None = None

        for entry in word.entries:
            if us_url is None and entry.us_audio:
                us_url = entry.us_audio[0]
            if uk_url is None and entry.uk_audio:
                uk_url = entry.uk_audio[0]
            if us_url is not None and uk_url is not None:
                break

        return us_url, uk_url
