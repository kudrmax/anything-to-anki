from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.infrastructure.adapters.cambridge.sqlite_reader import CambridgeSQLiteReader


class CambridgeCEFRSource(CEFRSource):
    """CEFR source backed by Cambridge Dictionary SQLite data.

    Uses the level of the first sense (primary meaning) as returned by
    Cambridge Dictionary.  Senses are stored in dictionary order where
    the first sense is the most common usage.
    """

    def __init__(self, reader: CambridgeSQLiteReader) -> None:
        self._reader = reader

    @property
    def name(self) -> str:
        return "Cambridge Dictionary"

    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        level_strings = self._reader.get_cefr_levels(lemma, pos_tag)
        if not level_strings:
            return {CEFRLevel.UNKNOWN: 1.0}

        # First sense = primary meaning in Cambridge order
        try:
            primary_level = CEFRLevel.from_str(level_strings[0])
        except ValueError:
            return {CEFRLevel.UNKNOWN: 1.0}

        return {primary_level: 1.0}
