"""The stored projection of card state, kept by the domain rules (spec §4, §5)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from backend.application.utils.card_state_calculator import (
    CardStateCalculator,
    CardStatusValues,
)
from backend.application.utils.changed_facts import ChangedFacts
from backend.domain.services.card_state_rules import newness_of
from backend.domain.value_objects.card_state_rows import CardStates
from backend.domain.value_objects.phrase_newness import NO_NEWNESS

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from backend.application.utils.user_knowledge_reader import UserKnowledgeReader
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.card_query import CardQuery
    from backend.domain.ports.card_state_store import CardStateStore
    from backend.domain.ports.change_recorder import ChangeRecorder
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.word_state_repository import WordStateRepository
    from backend.domain.value_objects.card_change import CardChange
    from backend.domain.value_objects.card_choice import WordState
    from backend.domain.value_objects.card_state_rows import (
        CardStateRow,
        PhraseWordRow,
        StoredCardState,
        StoredCardStates,
        WordStateRow,
    )
    from backend.domain.value_objects.review_card import CardRow, CardTargetRow


class ProjectorRecordedChangesError(RuntimeError):
    """The projector wrote facts that have owners: their changes would never be projected."""

    def __init__(self, changes: tuple[CardChange, ...]) -> None:
        super().__init__(f"the card state projector recorded changes: {changes}")


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
        recorder: ChangeRecorder,
    ) -> None:
        self._source_repo = source_repo
        self._card_query = card_query
        self._word_states = word_states
        self._knowledge = knowledge
        self._vocabulary = vocabulary
        self._store = store
        self._recorder = recorder

    def rebuild(self) -> None:
        """Every row computed anew over the whole database, all at one new revision."""
        states = self._all_states()
        self._store.replace_all(states, self._store.next_revision())

    def apply(self, changes: tuple[CardChange, ...]) -> None:
        """The rows the changes of the committing write touch, computed anew; each row whose
        values changed, removed or touched gets the one new revision of this write. The
        projection writes no facts, so it records no changes."""
        if changes:
            self._vocabulary.scope.invalidate()
            facts = ChangedFacts.of(changes)
            if facts.level_changed:
                self.rebuild()
            else:
                _Increment(
                    self._card_query, self._word_states, self._store, self._calculator(),
                ).apply(facts)
        recorded = self._recorder.drain()
        if recorded:
            raise ProjectorRecordedChangesError(recorded)

    def stored(self) -> StoredCardStates:
        """Every stored row, as it is now."""
        return self._store.read_all()

    def _calculator(self) -> CardStateCalculator:
        return CardStateCalculator(self._knowledge, self._vocabulary)

    def _all_states(self) -> CardStates:
        source_ids = [s.id for s in self._source_repo.list_all() if s.id is not None]
        words: dict[int, WordState] = {}
        for source_id in source_ids:
            words.update(self._word_states.of_source(source_id))
        calculator = self._calculator()
        cards: list[CardStateRow] = []
        phrase_words: list[PhraseWordRow] = []
        for rows in self._card_query.shown_cards(source_ids).values():
            for card in rows:
                card_words = calculator.phrase_words(card)
                status = calculator.status(words[card.word_id], card.phrase_id)
                cards.append(calculator.card(card, status, newness_of(card_words)))
                phrase_words.extend(card_words)
        return CardStates(
            cards=tuple(cards),
            words=tuple(calculator.word(word) for word in words.values()),
            phrase_words=tuple(phrase_words),
        )


class _Increment:
    """The changes of one write projected onto the stored rows.

    Three depths of work, each card at one of them:
    - read anew: the cards of the words a change of phrases or words reaches, every value
      and every other word computed from the facts;
    - own: the other cards of the words of a changed lemma, their status computed anew and
      their sections from their stored other words;
    - holding: the cards whose phrase holds a changed lemma, their sections computed anew
      from their stored other words and their stored status.
    """

    def __init__(
        self,
        card_query: CardQuery,
        word_states: WordStateRepository,
        store: CardStateStore,
        calculator: CardStateCalculator,
    ) -> None:
        self._card_query = card_query
        self._word_states = word_states
        self._store = store
        self._calculator = calculator
        self._cards: dict[int, CardStateRow] = {}
        self._removed: set[int] = set()
        self._words: dict[int, WordState] = {}
        self._stale_words: set[int] = set()
        self._stored: dict[int, StoredCardState] = {}

    def apply(self, facts: ChangedFacts) -> None:
        own_words = self._word_states.of_lemmas(facts.lemmas) if facts.lemmas else {}
        self._words.update(own_words)
        read_anew = self._read_anew(facts, own_words)
        if facts.lemmas:
            holding = self._renew_newness(facts)
            self._partly(own_words, holding - read_anew, read_anew)
        self._write(facts)

    def _stored_cards(self, phrase_ids: Collection[int]) -> dict[int, StoredCardState]:
        """The stored cards of these phrases as they were before this write, each read once."""
        missing = set(phrase_ids) - self._stored.keys()
        if missing:
            self._stored.update(self._store.cards(missing))
        return {pid: self._stored[pid] for pid in phrase_ids if pid in self._stored}

    # --- read anew ------------------------------------------------------------------------

    def _read_anew(self, facts: ChangedFacts, own_words: dict[int, WordState]) -> set[int]:
        """The cards of every word the changed phrases and words reach, computed whole;
        their stored cards no longer shown are removed. Returns the phrase ids handled."""
        store = self._store
        phrases = set(facts.phrases)
        word_ids: set[int] = set()
        for source_id in facts.deleted_sources:
            phrases |= {card.row.phrase_id for card in store.live_cards_of_source(source_id)}
            word_ids |= {word.word_id for word in store.words_of_source(source_id)}
        for source_id, lemmas in facts.source_words.items():
            word_ids |= {word.word_id for word in store.words_of_source(source_id, lemmas)}
            word_ids |= {
                word.word_id for word in own_words.values()
                if word.source_id == source_id and word.lemma.lower() in lemmas
            }
        stored = self._stored_cards(phrases)
        word_ids |= {card.row.word_id for card in stored.values() if not card.removed}
        word_ids |= {card.word_id for card in self._card_query.card_targets(phrases)}
        if not word_ids:
            return phrases
        self._load_words(word_ids)
        self._stale_words |= word_ids
        cards = self._card_query.shown_cards_of_words(word_ids)
        shown = self._compute_whole(cards)
        live = {pid for pid, card in stored.items() if not card.removed}
        live |= {card.row.phrase_id for card in store.live_cards_of_words(word_ids)}
        self._removed |= live - shown
        return shown | phrases

    def _compute_whole(self, cards: Iterable[CardRow]) -> set[int]:
        calculator = self._calculator
        phrase_words: list[PhraseWordRow] = []
        shown: set[int] = set()
        for card in cards:
            card_words = calculator.phrase_words(card)
            status = calculator.status(self._words[card.word_id], card.phrase_id)
            self._cards[card.phrase_id] = calculator.card(card, status, newness_of(card_words))
            phrase_words.extend(card_words)
            shown.add(card.phrase_id)
        self._store.replace_phrase_words(shown, phrase_words)
        return shown

    def _load_words(self, word_ids: Collection[int]) -> None:
        missing = set(word_ids) - self._words.keys()
        if missing:
            self._words.update(self._word_states.of_words(missing))

    # --- a changed lemma --------------------------------------------------------------------

    def _renew_newness(self, facts: ChangedFacts) -> set[int]:
        """The stored other words of the changed lemmas with their newness now; returns the
        phrases where one changed: no other card's new words did."""
        holding: set[int] = set()
        for kind in self._store.phrase_word_kinds(facts.lemmas):
            holding |= self._store.set_newness(kind, self._calculator.newness(kind))
        return holding

    def _partly(
        self, own_words: dict[int, WordState], holding: set[int], read_anew: set[int],
    ) -> None:
        """The own and holding cards not read anew, from their stored rows; a card with no
        live stored row is computed whole, and a stored card no longer shown is removed."""
        own_targets = self._card_query.card_targets_of_words(own_words.keys() - self._stale_words)
        holding -= {target.phrase_id for target in own_targets}
        targets = [
            *(t for t in own_targets if t.phrase_id not in read_anew),
            *self._card_query.card_targets(holding),
        ]
        shown = {target.phrase_id for target in targets}
        stored = self._stored_cards(shown | holding)
        self._removed |= {
            pid for pid in holding - shown if pid in stored and not stored[pid].removed
        }
        newness = self._store.phrase_newness(shown)
        whole: set[int] = set()
        for target in targets:
            kept = stored.get(target.phrase_id)
            if kept is None or kept.removed:
                whole.add(target.phrase_id)
                continue
            self._cards[target.phrase_id] = self._calculator.card(
                target,
                self._status(target, own_words, kept),
                newness.get(target.phrase_id, NO_NEWNESS),
            )
        if whole:
            cards = self._card_query.shown_cards_of_phrases(whole)
            self._load_words({card.word_id for card in cards})
            self._compute_whole(cards)

    def _status(
        self, target: CardTargetRow, own_words: dict[int, WordState], kept: StoredCardState,
    ) -> CardStatusValues:
        word = own_words.get(target.word_id)
        if word is None:
            return CardStatusValues.of(kept.row)
        return self._calculator.status(word, target.phrase_id)

    # --- writing ----------------------------------------------------------------------------

    def _write(self, facts: ChangedFacts) -> None:
        store = self._store
        before = self._stored_cards(self._cards.keys())
        changed: list[CardStateRow] = []
        sections: list[CardStateRow] = []
        for pid, row in self._cards.items():
            kept = before.get(pid)
            if kept is None or kept.removed:
                changed.append(row)
            elif kept.row != row:
                only_sections = kept.row == replace(
                    row, sections=kept.row.sections, new_counts=kept.row.new_counts,
                )
                (sections if only_sections else changed).append(row)
        removed = self._removed - self._cards.keys()
        touched = facts.content_phrases or facts.content_words
        if changed or sections or removed or touched:
            revision = store.next_revision()
            store.touch_cards(facts.content_phrases, facts.content_words, revision)
            store.write_cards(changed, revision)
            store.write_sections(sections, revision)
            store.remove_cards(removed, revision)
        self._write_words()

    def _write_words(self) -> None:
        word_ids = self._stale_words | self._words.keys()
        if not word_ids:
            return
        store = self._store
        before = store.words(word_ids)
        rows: list[WordStateRow] = [
            row for word_id, word in self._words.items()
            if before.get(word_id) != (row := self._calculator.word(word))
        ]
        store.write_words(rows)
        store.delete_words(before.keys() - self._words.keys())
