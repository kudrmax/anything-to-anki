"""Which review section a card belongs to, by what the user knows right now."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.candidate_section import CandidateSection

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
    from backend.domain.value_objects.user_knowledge import UserKnowledge

_JUNK_POS: frozenset[str] = frozenset({"INTJ"})
_MISSING_FROM_DICTIONARY_ZIPF: float = 0.0
_WORD_SEPARATOR = " "

SECTION_ORDER: dict[CandidateSection, int] = {
    CandidateSection.READY: 0,
    CandidateSection.EXTRA: 1,
    CandidateSection.PROBABLY_KNOWN: 2,
}


def new_words(candidate: StoredCandidate, knowledge: UserKnowledge | None) -> list[str]:
    """Words of the shown phrase besides the target that are new to the user, once each."""
    if knowledge is None:
        return []
    found: list[str] = []
    for word in candidate.phrase.other_words():
        if word.lemma not in found and knowledge.is_new(word):
            found.append(word.lemma)
    return found


def section_of(
    candidate: StoredCandidate,
    knowledge: UserKnowledge | None,
    frequent_threshold: FrequentWordThreshold | None,
) -> CandidateSection:
    if is_junk(candidate) or is_probably_known(candidate, frequent_threshold):
        return CandidateSection.PROBABLY_KNOWN
    if new_words(candidate, knowledge):
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
