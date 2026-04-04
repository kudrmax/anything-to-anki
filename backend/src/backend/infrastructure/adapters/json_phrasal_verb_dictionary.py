from __future__ import annotations

import json
from pathlib import Path

from backend.domain.ports.phrasal_verb_dictionary import PhrasalVerbDictionary

_DEFAULT_DATA_PATH = Path(__file__).parent / "phrasal_verbs.json"


class JsonPhrasalVerbDictionary(PhrasalVerbDictionary):
    """Phrasal verb dictionary loaded from a JSON list of 'verb particle' strings."""

    def __init__(self, data_path: Path = _DEFAULT_DATA_PATH) -> None:
        entries: list[str] = json.loads(data_path.read_text(encoding="utf-8"))
        self._lookup: frozenset[str] = frozenset(entries)

    def contains(self, verb_lemma: str, particle: str) -> bool:
        return f"{verb_lemma.lower()} {particle.lower()}" in self._lookup
