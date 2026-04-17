from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.infrastructure.adapters.cambridge.models import CambridgeEntry, CambridgeWord

# Penn Treebank POS tag → Cambridge POS string
_POS_TO_CAMBRIDGE: dict[str, str] = {
    "NN": "noun",
    "NNS": "noun",
    "NNP": "noun",
    "NNPS": "noun",
    "VB": "verb",
    "VBD": "verb",
    "VBG": "verb",
    "VBN": "verb",
    "VBP": "verb",
    "VBZ": "verb",
    "JJ": "adjective",
    "JJR": "adjective",
    "JJS": "adjective",
    "RB": "adverb",
    "RBR": "adverb",
    "RBS": "adverb",
    "UH": "exclamation",
    "MD": "modal verb",
    "IN": "preposition",
    "DT": "determiner",
    "PRP": "pronoun",
    "PRP$": "pronoun",
    "CC": "conjunction",
}


class CambridgeCEFRSource(CEFRSource):
    """CEFR source backed by Cambridge Dictionary data.

    Aggregates CEFR levels across senses using median.
    """

    def __init__(self, data: dict[str, CambridgeWord]) -> None:
        self._data = data

    @property
    def name(self) -> str:
        return "Cambridge Dictionary"

    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        word = self._data.get(lemma.lower())
        if word is None:
            return {CEFRLevel.UNKNOWN: 1.0}

        cambridge_pos = _POS_TO_CAMBRIDGE.get(pos_tag)
        entries = self._filter_entries_by_pos(word.entries, cambridge_pos)

        levels = self._collect_levels(entries)
        if not levels:
            return {CEFRLevel.UNKNOWN: 1.0}

        median = self._compute_median(levels)
        return {median: 1.0}

    def _filter_entries_by_pos(
        self,
        entries: list[CambridgeEntry],
        cambridge_pos: str | None,
    ) -> list[CambridgeEntry]:
        if cambridge_pos is None:
            return list(entries)
        matched = [e for e in entries if cambridge_pos in e.pos]
        if matched:
            return matched
        return list(entries)

    def _collect_levels(self, entries: list[CambridgeEntry]) -> list[CEFRLevel]:
        levels: list[CEFRLevel] = []
        for entry in entries:
            for sense in entry.senses:
                if sense.level:
                    try:
                        levels.append(CEFRLevel.from_str(sense.level))
                    except ValueError:
                        continue
        return levels

    @staticmethod
    def _compute_median(levels: list[CEFRLevel]) -> CEFRLevel:
        """Compute median CEFR level. For even count, pick lower-middle."""
        sorted_levels = sorted(levels, key=lambda lvl: lvl.value)
        mid = (len(sorted_levels) - 1) // 2
        return sorted_levels[mid]
