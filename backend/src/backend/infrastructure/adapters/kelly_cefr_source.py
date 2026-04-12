from __future__ import annotations

import csv
from pathlib import Path

from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.value_objects.cefr_level import CEFRLevel

_POS_TO_KELLY: dict[str, str] = {
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


class KellyCEFRSource(CEFRSource):
    """CEFR source backed by Kelly English frequency list."""

    def __init__(self, csv_path: Path) -> None:
        self._data: dict[tuple[str, str], CEFRLevel] = {}
        self._word_fallback: dict[str, CEFRLevel] = {}
        self._load(csv_path)

    def _load(self, csv_path: Path) -> None:
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                word = row["Word"].strip().lower()
                kelly_pos = row["Part of Speech"].strip().lower()
                cefr_raw = row["CEFR"].strip().strip('""\u201c\u201d').upper()
                if not word or not cefr_raw:
                    continue
                try:
                    level = CEFRLevel.from_str(cefr_raw)
                except ValueError:
                    continue
                self._data[(word, kelly_pos)] = level
                existing = self._word_fallback.get(word)
                if existing is None or level.value < existing.value:
                    self._word_fallback[word] = level

    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        word = lemma.lower()
        kelly_pos = _POS_TO_KELLY.get(pos_tag)

        if kelly_pos is not None:
            level = self._data.get((word, kelly_pos))
            if level is not None:
                return {level: 1.0}

        fallback = self._word_fallback.get(word)
        if fallback is not None:
            return {fallback: 1.0}

        return {CEFRLevel.UNKNOWN: 1.0}
