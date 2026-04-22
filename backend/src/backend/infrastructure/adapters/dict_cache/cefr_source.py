"""CEFRSource backed by the unified dictionary cache."""
from __future__ import annotations

from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.services.pos_mapping import map_pos_tag
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader


class DictCacheCEFRSource(CEFRSource):
    def __init__(self, reader: DictCacheReader, source_name: str) -> None:
        self._reader = reader
        self._source_name = source_name

    @property
    def name(self) -> str:
        return self._source_name

    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        unified_pos = map_pos_tag(pos_tag) or pos_tag
        raw = self._reader.get_cefr_distribution(lemma, unified_pos, self._source_name)
        if raw is None:
            return {CEFRLevel.UNKNOWN: 1.0}
        return {CEFRLevel.from_str(k): v for k, v in raw.items()}
