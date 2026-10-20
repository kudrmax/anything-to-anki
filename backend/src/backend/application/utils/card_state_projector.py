"""The stored projection of card state, kept by the domain rules (spec §4, §5)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.services.candidate_sections import new_counts_at_steps, sections_at_steps
from backend.domain.services.card_state_rules import changes_at, newness_of, phrase_word_rows
from backend.domain.services.card_view import card_status, open_elsewhere
from backend.domain.value_objects.card_choice import decision_status
from backend.domain.value_objects.card_state_rows import CardStateRow, CardStates, WordStateRow

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from backend.application.utils.user_knowledge_reader import UserKnowledgeReader
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.card_query import CardQuery
    from backend.domain.ports.card_state_store import CardStateStore
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.word_state_repository import WordStateRepository
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.card_choice import WordState
    from backend.domain.value_objects.card_state_rows import PhraseWordRow, StoredCardStates
    from backend.domain.value_objects.review_card import CardRow
    from backend.domain.value_objects.user_knowledge import KnowledgeBase


@dataclass(frozen=True)
class _SectionFacts:
    """What tells a card's section besides its phrase, done as its card status says."""

    lemma: str
    pos: str
    zipf_frequency: float
    is_done: bool
    earned_section: CandidateSection


class CardStateProjector:
    """The only writer of the projection. Reads the facts, what the user knows and `now`
    inside the caller's write transaction, so the rows match the state that commits."""

    def __init__(
        self,
        source_repo: SourceRepository,
        card_query: CardQuery,
        word_states: WordStateRepository,
        knowledge: UserKnowledgeReader,
        vocabulary: UserVocabulary,
        store: CardStateStore,
    ) -> None:
        self._source_repo = source_repo
        self._card_query = card_query
        self._word_states = word_states
        self._knowledge = knowledge
        self._vocabulary = vocabulary
        self._store = store

    def rebuild(self) -> None:
        """Every row computed anew over the whole database, all at one new revision."""
        states = self._all_states()
        self._store.replace_all(states, self._store.next_revision())

    def stored(self) -> StoredCardStates:
        """Every stored row, as it is now."""
        return self._store.read_all()

    def _all_states(self) -> CardStates:
        source_ids = [s.id for s in self._source_repo.list_all() if s.id is not None]
        words: dict[int, WordState] = {}
        for source_id in source_ids:
            words.update(self._word_states.of_source(source_id))
        cards = _Cards(words, self._knowledge.base(), self._vocabulary)
        for rows in self._card_query.shown_cards(source_ids).values():
            for row in rows:
                cards.add(row)
        return CardStates(
            cards=tuple(cards.rows),
            words=tuple(
                WordStateRow(
                    word_id=word.word_id, source_id=word.source_id, lemma=word.lemma.lower(),
                    status=decision_status(word),
                )
                for word in words.values()
            ),
            phrase_words=tuple(cards.phrase_words),
        )


class _Cards:
    """The rows of cards and their other words, computed one card at a time."""

    def __init__(
        self, words: Mapping[int, WordState], base: KnowledgeBase, vocabulary: UserVocabulary,
    ) -> None:
        self._words = words
        self._base = base
        self._vocabulary = vocabulary
        self._now: datetime = vocabulary.scope.now
        self.rows: list[CardStateRow] = []
        self.phrase_words: list[PhraseWordRow] = []

    def add(self, card: CardRow) -> None:
        word = self._words[card.word_id]
        lemma = self._vocabulary.of(card.lemma)
        status = card_status(word, card.phrase_id, lemma, open_elsewhere(word, lemma), self._now)
        phrase_words = phrase_word_rows(card.phrase_id, card.phrase, self._base)
        new_counts = new_counts_at_steps(newness_of(phrase_words))
        facts = _SectionFacts(
            lemma=card.lemma, pos=card.pos, zipf_frequency=card.zipf_frequency,
            is_done=status.is_done, earned_section=card.earned_section,
        )
        self.phrase_words.extend(phrase_words)
        self.rows.append(CardStateRow(
            phrase_id=card.phrase_id,
            source_id=card.source_id,
            word_id=card.word_id,
            lemma=card.lemma.lower(),
            is_done=status.is_done,
            wants_generation=status.wants_generation,
            sections=sections_at_steps(facts, new_counts),
            new_counts=new_counts,
            changes_at=changes_at(lemma, self._now),
        ))
