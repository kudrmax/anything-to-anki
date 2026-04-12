from __future__ import annotations

import csv
from pathlib import Path

from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.value_objects.cefr_level import CEFRLevel

_POS_TO_OXFORD: dict[str, str] = {
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


class OxfordCEFRSource(CEFRSource):
    """CEFR source backed by Oxford 5000 CSV data."""

    def __init__(self, csv_path: Path) -> None:
        self._data: dict[tuple[str, str], CEFRLevel] = {}
        self._word_fallback: dict[str, CEFRLevel] = {}
        self._load(csv_path)

    def _load(self, csv_path: Path) -> None:
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                word = row["word"].strip().lower()
                oxford_type = row["type"].strip().lower()
                cefr_str = row["cefr"].strip().upper()
                try:
                    level = CEFRLevel.from_str(cefr_str)
                except ValueError:
                    continue
                self._data[(word, oxford_type)] = level
                existing = self._word_fallback.get(word)
                if existing is None or level.value < existing.value:
                    self._word_fallback[word] = level

    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        word = lemma.lower()
        oxford_type = _POS_TO_OXFORD.get(pos_tag)

        if oxford_type is not None:
            level = self._data.get((word, oxford_type))
            if level is not None:
                return {level: 1.0}

        fallback = self._word_fallback.get(word)
        if fallback is not None:
            return {fallback: 1.0}

        return {CEFRLevel.UNKNOWN: 1.0}
