"""PronunciationSource backed by the unified dictionary cache."""
from __future__ import annotations

from backend.domain.ports.pronunciation_source import PronunciationSource
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader


class DictCachePronunciationSource(PronunciationSource):
    def __init__(self, reader: DictCacheReader) -> None:
        self._reader = reader

    def get_audio_urls(self, lemma: str) -> tuple[str | None, str | None]:
        return self._reader.get_audio_urls(lemma)
