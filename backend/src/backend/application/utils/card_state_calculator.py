"""The rows of the card state projection computed from the facts by the domain rules, one
card at a time: the same code for the full rebuild and for the changes of one write."""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Protocol

from backend.domain.services.candidate_sections import new_counts_at_steps, sections_at_steps
from backend.domain.services.card_state_rules import changes_at, phrase_word_rows
from backend.domain.services.card_view import card_status, open_elsewhere
from backend.domain.value_objects.card_choice import decision_status
from backend.domain.value_objects.card_state_rows import CardStateRow, WordStateRow
from backend.domain.value_objects.user_knowledge import RememberedNewness

if TYPE_CHECKING:
    from datetime import datetime

    from backend.application.utils.user_knowledge_reader import UserKnowledgeReader
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.card_choice import WordState
    from backend.domain.value_objects.card_state_rows import PhraseWordRow
    from backend.domain.value_objects.phrase_newness import PhraseNewness
    from backend.domain.value_objects.review_card import CardRow
    from backend.domain.value_objects.user_knowledge import KnowledgeBase, Newness, NewnessFacts


class CardTarget(Protocol):
    """A shown card's facts besides its phrase: its word and the section its phrase earned."""

    @property
    def source_id(self) -> int: ...

    @property
    def word_id(self) -> int: ...

    @property
    def phrase_id(self) -> int: ...

    @property
    def lemma(self) -> str: ...

    @property
    def pos(self) -> str: ...

    @property
    def zipf_frequency(self) -> float: ...

    @property
    def earned_section(self) -> CandidateSection: ...


@dataclass(frozen=True)
class CardStatusValues:
    """The values of a card row that its word and its lemma tell."""

    is_done: bool
    wants_generation: bool
    changes_at: datetime | None

    @staticmethod
    def of(row: CardStateRow) -> CardStatusValues:
        return CardStatusValues(row.is_done, row.wants_generation, row.changes_at)


@dataclass(frozen=True)
class _SectionFacts:
    """What tells a card's section besides its phrase, done as its card status says."""

    lemma: str
    pos: str
    zipf_frequency: float
    is_done: bool
    earned_section: CandidateSection


class CardStateCalculator:
    """What the user knows and `now` read once, at the first rule that needs them."""

    def __init__(self, knowledge: UserKnowledgeReader, vocabulary: UserVocabulary) -> None:
        self._knowledge = knowledge
        self._vocabulary = vocabulary

    @cached_property
    def _base(self) -> KnowledgeBase:
        return self._knowledge.base()

    @cached_property
    def _now(self) -> datetime:
        return self._vocabulary.scope.now

    def status(self, word: WordState, phrase_id: int) -> CardStatusValues:
        lemma = self._vocabulary.of(word.lemma)
        status = card_status(word, phrase_id, lemma, open_elsewhere(word, lemma), self._now)
        return CardStatusValues(
            is_done=status.is_done,
            wants_generation=status.wants_generation,
            changes_at=changes_at(lemma, self._now),
        )

    @cached_property
    def _newness(self) -> RememberedNewness:
        return RememberedNewness(self._base)

    def phrase_words(self, card: CardRow) -> tuple[PhraseWordRow, ...]:
        return phrase_word_rows(card.phrase_id, card.phrase, self._newness)

    def newness(self, word: NewnessFacts) -> Newness:
        return self._newness.newness(word)

    @staticmethod
    def card(
        target: CardTarget, status: CardStatusValues, newness: PhraseNewness,
    ) -> CardStateRow:
        """`newness`: of the other words of the card's phrase."""
        new_counts = new_counts_at_steps(newness)
        facts = _SectionFacts(
            lemma=target.lemma, pos=target.pos, zipf_frequency=target.zipf_frequency,
            is_done=status.is_done, earned_section=target.earned_section,
        )
        return CardStateRow(
            phrase_id=target.phrase_id,
            source_id=target.source_id,
            word_id=target.word_id,
            lemma=target.lemma.lower(),
            is_done=status.is_done,
            wants_generation=status.wants_generation,
            sections=sections_at_steps(facts, new_counts),
            new_counts=new_counts,
            changes_at=status.changes_at,
        )

    @staticmethod
    def word(word: WordState) -> WordStateRow:
        return WordStateRow(
            word_id=word.word_id, source_id=word.source_id, lemma=word.lemma.lower(),
            status=decision_status(word),
        )
