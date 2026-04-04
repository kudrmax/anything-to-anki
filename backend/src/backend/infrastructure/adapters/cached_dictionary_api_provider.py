from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from backend.domain.entities.dictionary_entry import DictionaryEntry
from backend.domain.ports.dictionary_provider import DictionaryProvider
from backend.infrastructure.persistence.dictionary_cache import DictionaryCacheRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_API_BASE = "https://api.dictionaryapi.dev/api/v2/entries/en"

_POS_MAP: dict[str, str] = {
    "NOUN": "noun",
    "VERB": "verb",
    "ADJ": "adjective",
    "ADV": "adverb",
}

_NO_DEFINITION = "No definition found"


def _parse_response(lemma: str, pos: str, data: list[dict]) -> DictionaryEntry:  # type: ignore[type-arg]
    api_pos = _POS_MAP.get(pos.upper())

    # Extract IPA from first phonetic with a non-empty text
    ipa: str | None = None
    for phonetic in data[0].get("phonetics", []):
        if phonetic.get("text"):
            ipa = phonetic["text"]
            break

    # Collect all meanings
    meanings: list[dict] = []  # type: ignore[type-arg]
    for entry in data:
        meanings.extend(entry.get("meanings", []))

    # Try to find matching POS first, fall back to first available
    definition: str | None = None
    for meaning in meanings:
        if api_pos and meaning.get("partOfSpeech") == api_pos:
            defs = meaning.get("definitions", [])
            if defs:
                definition = defs[0].get("definition", "")
                break

    if definition is None:
        for meaning in meanings:
            defs = meaning.get("definitions", [])
            if defs:
                definition = defs[0].get("definition", "")
                break

    return DictionaryEntry(
        lemma=lemma,
        pos=pos,
        definition=definition or _NO_DEFINITION,
        ipa=ipa,
    )


class CachedDictionaryApiProvider(DictionaryProvider):
    """Fetches definitions from Free Dictionary API with SQLite caching."""

    def __init__(self, session: Session) -> None:
        self._cache = DictionaryCacheRepository(session)

    def get_entry(self, lemma: str, pos: str) -> DictionaryEntry:
        cached = self._cache.get(lemma, pos)
        if cached is not None:
            return cached

        entry = self._fetch(lemma, pos)
        self._cache.save(entry)
        return entry

    def _fetch(self, lemma: str, pos: str) -> DictionaryEntry:
        try:
            response = httpx.get(f"{_API_BASE}/{lemma}", timeout=5.0)
            if response.status_code == 200:
                return _parse_response(lemma, pos, response.json())
        except Exception:  # noqa: BLE001
            pass
        return DictionaryEntry(lemma=lemma, pos=pos, definition=_NO_DEFINITION, ipa=None)
