from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.infrastructure.adapters.cambridge.sqlite_reader import CambridgeSQLiteReader


class CambridgeCEFRSource(CEFRSource):
    """CEFR source backed by Cambridge Dictionary SQLite data."""

    def __init__(self, reader: CambridgeSQLiteReader) -> None:
        self._reader = reader

    @property
    def name(self) -> str:
        return "Cambridge Dictionary"

    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        level_strings = self._reader.get_cefr_levels(lemma, pos_tag)
        if not level_strings:
            return {CEFRLevel.UNKNOWN: 1.0}

        levels: list[CEFRLevel] = []
        for s in level_strings:
            try:
                levels.append(CEFRLevel.from_str(s))
            except ValueError:
                continue

        if not levels:
            return {CEFRLevel.UNKNOWN: 1.0}

        median = self._compute_median(levels)
        return {median: 1.0}

    @staticmethod
    def _compute_median(levels: list[CEFRLevel]) -> CEFRLevel:
        sorted_levels = sorted(levels, key=lambda lvl: lvl.value)
        mid = (len(sorted_levels) - 1) // 2
        return sorted_levels[mid]
