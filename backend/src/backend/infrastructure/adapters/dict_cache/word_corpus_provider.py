from __future__ import annotations

from backend.domain.ports.word_corpus_provider import WordCorpusProvider
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader


class DictCacheWordCorpusProvider(WordCorpusProvider):
    """WordCorpusProvider backed by the dictionary cache."""

    def __init__(self, reader: DictCacheReader) -> None:
        self._reader = reader

    def get_all_lemma_pos_pairs(self) -> list[tuple[str, str]]:
        return self._reader.get_all_lemma_pos_pairs()
