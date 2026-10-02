"""Choosing a context phrase for a topic target.

A topic has no text of its own, so its phrases are borrowed from the sources
the user already added. Preference order: a phrase that the pipeline already
cut out for the same lemma, then a sentence containing the target verbatim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.stored_candidate import StoredCandidate

CLEAN_PURITY = "clean"
MIN_SENTENCE_WORDS = 4
MAX_SENTENCE_WORDS = 30

_MARKED_TARGET = re.compile(r"\*\*(.+?)\*\*")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s+|\n+")


@dataclass(frozen=True)
class MarkedPhrase:
    """A sentence and the target inside it."""

    text: str
    target: str


@dataclass(frozen=True)
class FoundSentence:
    """A sentence from a text that contains the target verbatim."""

    text: str
    target: str


def parse_marked_phrase(marked: str) -> MarkedPhrase | None:
    """Split a sentence with a **bold** target into plain text and the target."""
    match = _MARKED_TARGET.search(marked)
    if match is None:
        return None
    target = match.group(1).strip()
    text = _MARKED_TARGET.sub(lambda m: m.group(1), marked).strip()
    if not target or not text:
        return None
    return MarkedPhrase(text=text, target=target)


def _word_count(text: str) -> int:
    return len(text.split())


def pick_best_candidate_phrase(
    candidates: Iterable[StoredCandidate],
) -> StoredCandidate | None:
    """Pick the phrase that is easiest to learn from: clean first, then shortest."""
    return min(
        candidates,
        key=lambda c: (c.fragment_purity != CLEAN_PURITY, _word_count(c.context_fragment)),
        default=None,
    )


def _target_pattern(variants: Iterable[str]) -> re.Pattern[str] | None:
    alternatives = sorted(
        {r"\s+".join(re.escape(word) for word in v.split()) for v in variants if v.strip()},
        key=len,
        reverse=True,
    )
    if not alternatives:
        return None
    return re.compile(r"\b(" + "|".join(alternatives) + r")\b", re.IGNORECASE)


def find_shortest_sentence(text: str, variants: Iterable[str]) -> FoundSentence | None:
    """Find the shortest sentence of a readable length containing any variant."""
    pattern = _target_pattern(variants)
    if pattern is None:
        return None
    best: FoundSentence | None = None
    for raw in _SENTENCE_BOUNDARY.split(text):
        sentence = " ".join(raw.split())
        words = _word_count(sentence)
        if not MIN_SENTENCE_WORDS <= words <= MAX_SENTENCE_WORDS:
            continue
        match = pattern.search(sentence)
        if match is None:
            continue
        if best is None or words < _word_count(best.text):
            best = FoundSentence(text=sentence, target=match.group(1))
    return best
