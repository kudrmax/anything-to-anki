"""Which review section a card belongs to, by what the user knows right now.

A card is a shown phrase of a word: a done card is Reviewed; an open card's section goes by
the words of that phrase and the facts of the word, so cards of one word may sit in
different sections.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from backend.domain.services.card_view import section, shown_section
from backend.domain.value_objects.by_step import NewCountsByStep, SectionsByStep
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.frequent_word_threshold import THRESHOLD_STEPS, is_frequent
from backend.domain.value_objects.phrase_newness import NO_NEWNESS, PhraseNewness

if TYPE_CHECKING:
    from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.user_knowledge import KnowledgeBase, UserKnowledge

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


class SectionFacts(WordFacts, Protocol):
    """What tells a card's section besides the words of its phrase."""

    @property
    def is_done(self) -> bool: ...

    @property
    def earned_section(self) -> CandidateSection:
        """The section the card's phrase earned when it was added or its text last changed."""
        ...


class ShownCardFacts(CardFacts, SectionFacts, Protocol):
    """A shown card: its phrase and what tells its section."""


def phrase_newness(phrase: Phrase, knowledge_base: KnowledgeBase | None) -> PhraseNewness:
    """The newness of the words of the phrase besides the target; none without knowledge."""
    if knowledge_base is None:
        return NO_NEWNESS
    return PhraseNewness.of(
        (word.lemma, word.zipf, knowledge_base.newness(word)) for word in phrase.other_words()
    )


def new_words(phrase: Phrase, knowledge: UserKnowledge | None) -> list[str]:
    """Words of the phrase besides the target that are new to the user, once each.
    Words the user is learning count as new."""
    if knowledge is None:
        return []
    return phrase_newness(phrase, knowledge.base).new_lemmas(knowledge.frequent_zipf)


def section_of(
    card: CardFacts,
    knowledge: UserKnowledge | None,
    frequent_threshold: FrequentWordThreshold | None,
) -> CandidateSection:
    """The section the phrase earns, done or not."""
    return _earned_section(
        card,
        phrase_newness(card.phrase, knowledge.base if knowledge is not None else None),
        target_step=frequent_threshold.zipf if frequent_threshold is not None else None,
        words_step=knowledge.frequent_zipf if knowledge is not None else None,
    )


def open_section(
    card: ShownCardFacts,
    knowledge: UserKnowledge | None,
    frequent_threshold: FrequentWordThreshold | None,
) -> CandidateSection:
    """Where the card stands, done or not: Ready only if the phrase is Ready now and earned it."""
    return shown_section(section_of(card, knowledge, frequent_threshold), card.earned_section)


def card_section(
    card: ShownCardFacts,
    knowledge: UserKnowledge | None,
    frequent_threshold: FrequentWordThreshold | None,
) -> CandidateSection:
    """Where the card stands: Reviewed once done, else its open section."""
    return section(card, open_section(card, knowledge, frequent_threshold))


def sections_by_step(
    card: ShownCardFacts, knowledge_base: KnowledgeBase | None,
) -> tuple[CandidateSection, ...]:
    """`card_section` at every threshold of THRESHOLD_STEPS, in its order, the phrase read
    once."""
    newness = phrase_newness(card.phrase, knowledge_base)
    return sections_at_steps(card, new_counts_at_steps(newness)).sections


def sections_at_steps(card: SectionFacts, new_counts: NewCountsByStep) -> SectionsByStep:
    """`card_section` at every threshold step, given how many other words of the card's
    phrase are new at each."""
    return SectionsByStep(tuple(
        section(
            card,
            shown_section(
                _earned_by_count(card, new_counts.at(step), target_step=step),
                card.earned_section,
            ),
        )
        for step in THRESHOLD_STEPS
    ))


def new_counts_at_steps(newness: PhraseNewness) -> NewCountsByStep:
    """How many words besides the target are new at every threshold step."""
    return NewCountsByStep(newness.counts(THRESHOLD_STEPS))


def _earned_section(
    card: WordFacts,
    newness: PhraseNewness,
    *,
    target_step: float | None,
    words_step: float | None,
) -> CandidateSection:
    """`target_step` tells whether the target is probably known, `words_step` — which other
    words of the phrase are new."""
    return _earned_by_count(card, newness.count(words_step), target_step=target_step)


def _earned_by_count(
    card: WordFacts, new_count: int, *, target_step: float | None,
) -> CandidateSection:
    """`new_count`: how many other words of the phrase are new."""
    if is_junk(card) or is_frequent(card.zipf_frequency, target_step):
        return CandidateSection.PROBABLY_KNOWN
    if new_count:
        return CandidateSection.EXTRA
    return CandidateSection.READY


@dataclass(frozen=True)
class _PhraseOfWord:
    """A word shown in a phrase: what `section_of` reads of a card."""

    word: WordFacts
    phrase: Phrase

    @property
    def lemma(self) -> str:
        return self.word.lemma

    @property
    def pos(self) -> str:
        return self.word.pos

    @property
    def zipf_frequency(self) -> float:
        return self.word.zipf_frequency


@dataclass(frozen=True)
class SectionRule:
    """What the user knows at one moment, to tell the section a phrase earns."""

    knowledge: UserKnowledge | None
    frequent_threshold: FrequentWordThreshold | None

    def earned(self, phrase: Phrase, word: WordFacts) -> CandidateSection:
        return section_of(_PhraseOfWord(word, phrase), self.knowledge, self.frequent_threshold)


def is_junk(word: WordFacts) -> bool:
    """Interjections and words missing from the frequency dictionary."""
    if word.pos in _JUNK_POS:
        return True
    is_single_word = _WORD_SEPARATOR not in word.lemma
    return is_single_word and word.zipf_frequency <= _MISSING_FROM_DICTIONARY_ZIPF
