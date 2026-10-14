"""Choosing a context phrase for a topic target.

A topic has no text of its own, so its phrases are borrowed from the sources
the user already added. Preference order: a phrase that the pipeline already
cut out for the same lemma, then a sentence containing the target verbatim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.services.candidate_sections import new_words

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.user_knowledge import UserKnowledge

MIN_SENTENCE_WORDS = 4
MAX_SENTENCE_WORDS = 30

_MARKED_TARGET = re.compile(r"\*\*(.+?)\*\*")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s+|\n+")


@dataclass(frozen=True)
class MarkedPhrase:
    """A sentence and the target inside it: its text and where the bold parts stand."""

    text: str
    target: str
    spans: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class FoundSentence:
    """A sentence from a text that contains the target verbatim."""

    text: str
    target: str


def parse_marked_phrase(marked: str) -> MarkedPhrase | None:
    """Split a sentence with a **bold** target into plain text, the target and its place."""
    text = ""
    parts: list[str] = []
    spans: list[tuple[int, int]] = []
    position = 0
    for match in _MARKED_TARGET.finditer(marked):
        text += marked[position:match.start()]
        part = match.group(1)
        lead = len(part) - len(part.lstrip())
        start = len(text) + lead
        end = start + len(part.strip())
        if end > start:
            parts.append(part.strip())
            spans.append((start, end))
        text += part
        position = match.end()
    text += marked[position:]
    stripped = text.strip()
    if not spans or not stripped:
        return None
    shift = len(text) - len(text.lstrip())
    return MarkedPhrase(
        text=stripped,
        target=" ".join(parts),
        spans=tuple((start - shift, end - shift) for start, end in spans),
    )


def _word_count(text: str) -> int:
    return len(text.split())


def pick_best_candidate_phrase(
    candidates: Iterable[StoredCandidate],
    knowledge: UserKnowledge,
) -> StoredCandidate | None:
    """Pick the phrase that is easiest to learn from: fewest new words, then shortest."""
    return min(
        candidates,
        key=lambda c: (len(new_words(c.phrase, knowledge)), len(c.phrase.words)),
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
