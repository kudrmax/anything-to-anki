"""Which review section a card belongs to, by what the user knows right now."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.candidate_section import CandidateSection

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
    from backend.domain.value_objects.vocabulary import Vocabulary

_JUNK_POS: frozenset[str] = frozenset({"INTJ"})
_MISSING_FROM_DICTIONARY_ZIPF: float = 0.0
_WORD_SEPARATOR = " "

SECTION_ORDER: dict[CandidateSection, int] = {
    CandidateSection.READY: 0,
    CandidateSection.EXTRA: 1,
    CandidateSection.PROBABLY_KNOWN: 2,
}


def extra_words(candidate: StoredCandidate, vocabulary: Vocabulary) -> list[str]:
    """Words of the phrase besides the target the user probably doesn't know.

    A word is new when the user said so, or when it is rare and the user
    didn't say they know it.
    """
    if candidate.phrase_words is None:
        return []
    found: list[str] = []
    for word in candidate.phrase_words.words:
        if word.lemma in found:
            continue
        if vocabulary.is_unknown(word.lemma) or (
            word.rare and not vocabulary.is_known(word.lemma)
        ):
            found.append(word.lemma)
    return found


def section_of(
    candidate: StoredCandidate,
    vocabulary: Vocabulary,
    frequent_threshold: FrequentWordThreshold | None,
) -> CandidateSection:
    if is_junk(candidate) or is_probably_known(candidate, frequent_threshold):
        return CandidateSection.PROBABLY_KNOWN
    if extra_words(candidate, vocabulary):
        return CandidateSection.EXTRA
    return CandidateSection.READY


def is_probably_known(
    candidate: StoredCandidate,
    frequent_threshold: FrequentWordThreshold | None,
) -> bool:
    return frequent_threshold is not None and frequent_threshold.covers(candidate.zipf_frequency)


def is_junk(candidate: StoredCandidate) -> bool:
    """Interjections and words missing from the frequency dictionary."""
    if candidate.pos in _JUNK_POS:
        return True
    is_single_word = _WORD_SEPARATOR not in candidate.lemma
    return is_single_word and candidate.zipf_frequency <= _MISSING_FROM_DICTIONARY_ZIPF
