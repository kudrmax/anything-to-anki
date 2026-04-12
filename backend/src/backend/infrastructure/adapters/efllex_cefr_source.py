from __future__ import annotations

import csv
from pathlib import Path

from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.value_objects.cefr_level import CEFRLevel

_LEVEL_COLUMNS: list[tuple[str, CEFRLevel]] = [
    ("level_freq@a1", CEFRLevel.A1),
    ("level_freq@a2", CEFRLevel.A2),
    ("level_freq@b1", CEFRLevel.B1),
    ("level_freq@b2", CEFRLevel.B2),
    ("level_freq@c1", CEFRLevel.C1),
]


class EFLLexCEFRSource(CEFRSource):
    """CEFR source backed by EFLLex TSV data."""

    def __init__(self, tsv_path: Path) -> None:
        self._data: dict[tuple[str, str], dict[CEFRLevel, float]] = {}
        self._load(tsv_path)

    def _load(self, tsv_path: Path) -> None:
        with open(tsv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                word = row["word"].lower()
                tag = row["tag"].strip()
                freqs: dict[CEFRLevel, float] = {}
                total = 0.0
                for col_name, level in _LEVEL_COLUMNS:
                    val = float(row[col_name])
                    if val > 0:
                        freqs[level] = val
                        total += val
                if total > 0:
                    self._data[(word, tag)] = {
                        lvl: freq / total for lvl, freq in freqs.items()
                    }

    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        dist = self._data.get((lemma.lower(), pos_tag))
        if dist is not None:
            return dist
        return {CEFRLevel.UNKNOWN: 1.0}
