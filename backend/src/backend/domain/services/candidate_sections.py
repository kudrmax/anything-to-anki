"""Which review section a card belongs to, by what the user knows right now.

A card is a shown phrase of a word: a done card is Reviewed; an open card's section goes by
the words of that phrase and the facts of the word, so cards of one word may sit in
different sections.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from backend.domain.services.card_view import section
from backend.domain.value_objects.candidate_section import CandidateSection

if TYPE_CHECKING:
    from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.user_knowledge import UserKnowledge

_JUNK_POS: frozenset[str] = frozenset({"INTJ"})
_MISSING_FROM_DICTIONARY_ZIPF: float = 0.0
_WORD_SEPARATOR = " "

SECTION_ORDER: dict[CandidateSection, int] = {
    CandidateSection.READY: 0,
    CandidateSection.EXTRA: 1,
    CandidateSection.PROBABLY_KNOWN: 2,
    CandidateSection.REVIEWED: 3,
}


class WordFacts(Protocol):
    @property
    def lemma(self) -> str: ...

    @property
    def pos(self) -> str: ...

    @property
    def zipf_frequency(self) -> float: ...


class CardFacts(WordFacts, Protocol):
    @property
    def phrase(self) -> Phrase:
        """The phrase the card shows."""
        ...


class ShownCardFacts(CardFacts, Protocol):
    @property
    def is_done(self) -> bool: ...


def new_words(phrase: Phrase, knowledge: UserKnowledge | None) -> list[str]:
    """Words of the phrase besides the target that are new to the user, once each.
    Words the user is learning count as new."""
    if knowledge is None:
        return []
    found: list[str] = []
    for word in phrase.other_words():
        if word.lemma not in found and knowledge.is_new(word):
            found.append(word.lemma)
    return found


def section_of(
    card: CardFacts,
    knowledge: UserKnowledge | None,
    frequent_threshold: FrequentWordThreshold | None,
) -> CandidateSection:
    """The section the phrase earns, done or not."""
    if is_junk(card) or is_probably_known(card, frequent_threshold):
        return CandidateSection.PROBABLY_KNOWN
    if new_words(card.phrase, knowledge):
        return CandidateSection.EXTRA
    return CandidateSection.READY


def card_section(
    card: ShownCardFacts,
    knowledge: UserKnowledge | None,
    frequent_threshold: FrequentWordThreshold | None,
) -> CandidateSection:
    """Where the card stands: Reviewed once done, else the section its phrase earns."""
    return section(card, section_of(card, knowledge, frequent_threshold))


def is_probably_known(
    word: WordFacts,
    frequent_threshold: FrequentWordThreshold | None,
) -> bool:
    return frequent_threshold is not None and frequent_threshold.covers(word.zipf_frequency)


def is_junk(word: WordFacts) -> bool:
    """Interjections and words missing from the frequency dictionary."""
    if word.pos in _JUNK_POS:
        return True
    is_single_word = _WORD_SEPARATOR not in word.lemma
    return is_single_word and word.zipf_frequency <= _MISSING_FROM_DICTIONARY_ZIPF
