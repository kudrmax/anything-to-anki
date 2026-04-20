from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.pronunciation_source import PronunciationSource

if TYPE_CHECKING:
    from backend.infrastructure.adapters.cambridge.sqlite_reader import CambridgeSQLiteReader


class CambridgePronunciationSource(PronunciationSource):
    """Pronunciation audio URL lookup from Cambridge Dictionary SQLite data."""

    def __init__(self, reader: CambridgeSQLiteReader) -> None:
        self._reader = reader

    def get_audio_urls(self, lemma: str) -> tuple[str | None, str | None]:
        return self._reader.get_audio_urls(lemma)
