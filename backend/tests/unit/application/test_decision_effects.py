"""DecisionEffects: what follows each row, call by call, over fakes."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, call

import pytest
from backend.application.utils.decision_effects import DecisionEffects
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.entities.word_decision import WordDecision
from backend.domain.exceptions import SourceOperationBusyError
from backend.domain.services.decision_rules import BindingRef, on_bind, press
from backend.domain.value_objects.anki_binding import AnkiBinding
from backend.domain.value_objects.card_choice import (
    Binding,
    CardChoice,
    CardState,
    NoteKind,
    Press,
    WordState,
)
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.word_status import WordStatus

from tests.decision_support import NOW
from tests.lock_support import free_lock
from tests.vocabulary_support import user_vocabulary

pytestmark = pytest.mark.unit

LEMMA = "glare"
CARD = 11
OTHER_CARD = 21
ORPHAN = 501
DUE = NOW - LEARNING_KNOWN_AFTER
FRESH = NOW - timedelta(days=1)


def _word(choice: CardChoice, binding: Binding | None = None, *, word_id: int = 1) -> WordState:
    card = CARD if word_id == 1 else OTHER_CARD
    return WordState(word_id, LEMMA, "VERB", word_id, (CardState(card, choice, binding),))


def _facts(*, phrasal: bool = False) -> StoredCandidate:
    return StoredCandidate(
        id=1, source_id=1, lemma=LEMMA, pos="VERB", cefr_level="B2", zipf_frequency=3.0,
        occurrences=1, status=WordStatus.NEW, is_phrasal_verb=phrasal,
    )


class Bench:
    def __init__(self, *, known: set[tuple[str, str | None]] | None = None) -> None:
        self.known = MagicMock()
        self.known.known_lemmas.return_value = {lemma for lemma, _ in known or set()}
        self.vocabulary = user_vocabulary(self.known)
        self.words = MagicMock()
        self.words.of_lemma.return_value = []
        self.decisions = MagicMock()
        self.anki_sync = MagicMock()
        self.anki_sync.orphans.return_value = []
        self.lock = free_lock()
        self.effects = DecisionEffects(
            word_states=self.words, vocabulary=self.vocabulary, decision_repo=self.decisions,
            anki_sync=self.anki_sync, lock=self.lock,
        )

    def press(self, word: WordState, button: Press, **facts: bool) -> None:
        knowledge = self.vocabulary.of(LEMMA)
        outcome = press(word, CARD, button, knowledge, None, NOW)
        self.effects.apply(word, outcome, _facts(**facts))


def test_known_saves_marks_known_and_calibrates() -> None:
    bench = Bench()
    word = _word(CardChoice.NONE)

    bench.press(word, Press.KNOWN)

    bench.words.save.assert_called_once_with(word.with_cards(CardState(CARD, CardChoice.KNOWN)))
    bench.known.mark_known.assert_called_once_with(LEMMA, "VERB")
    bench.decisions.record.assert_called_once_with(
        WordDecision(lemma=LEMMA, zipf_frequency=3.0, is_known=True),
    )


def test_a_choice_only_change_saves_the_choice_and_nothing_else() -> None:
    bench = Bench()

    bench.press(_word(CardChoice.LEARN), Press.CLOZE)

    bench.words.save.assert_called_once()
    bench.decisions.record.assert_not_called()
    bench.known.mark_known.assert_not_called()


def test_a_phrasal_verb_is_not_calibrated() -> None:
    bench = Bench()

    bench.press(_word(CardChoice.NONE), Press.LEARN, phrasal=True)

    bench.decisions.record.assert_not_called()


def test_a_release_releases_the_cards_binding_now() -> None:
    bench = Bench()

    bench.press(_word(CardChoice.LEARN, Binding(NoteKind.LEARN, FRESH)), Press.LEARN)

    bench.anki_sync.release.assert_called_once_with([CARD], NOW)
    bench.decisions.forget.assert_called_once_with(LEMMA)


def test_an_export_binds_the_card_to_its_note() -> None:
    bench = Bench()
    word = _word(CardChoice.CLOZE)
    outcome = on_bind(word, CARD, bench.vocabulary.of(LEMMA), NOW)

    bench.effects.apply(word, outcome, _facts(), note_id=777)

    bench.anki_sync.bind.assert_called_once_with(AnkiBinding(
        word_id=1, phrase_id=CARD, note_id=777, lemma=LEMMA, pos="VERB",
        note_kind=NoteKind.CLOZE, learning_since=NOW,
    ))
    bench.words.save.assert_called_once_with(outcome.word)


def test_an_export_without_its_note_is_a_bug() -> None:
    bench = Bench()
    word = _word(CardChoice.LEARN)
    outcome = on_bind(word, CARD, bench.vocabulary.of(LEMMA), NOW)

    with pytest.raises(AssertionError):
        bench.effects.apply(word, outcome, _facts())


class TestKnownRemoval:
    def _bench(self) -> tuple[Bench, WordState, WordState]:
        bench = Bench(known={(LEMMA, "VERB"), (LEMMA, "NOUN")})
        acting = _word(CardChoice.KNOWN)
        other = _word(CardChoice.KNOWN, Binding(NoteKind.LEARN, FRESH), word_id=2)
        bench.words.of_lemma.return_value = [acting, other]
        bench.anki_sync.orphans.return_value = [
            BindingRef(ORPHAN, DUE, CardChoice.LEARN), BindingRef(502, FRESH, CardChoice.LEARN),
        ]
        return bench, acting, other

    def test_undo_of_known_forgets_every_pos_and_revokes_every_other_known_card(
        self,
    ) -> None:
        bench, acting, other = self._bench()

        bench.press(acting, Press.KNOWN)

        bench.known.remove_known.assert_called_once_with(LEMMA)
        saved = [c.args[0] for c in bench.words.save.call_args_list]
        assert saved == [
            acting.with_cards(CardState(CARD, CardChoice.NONE)),
            other.with_cards(CardState(OTHER_CARD, CardChoice.NONE)),
        ], "the acting word's outcome is its press; the cascade reads the others"
        assert bench.anki_sync.release.call_args_list == [call([OTHER_CARD], NOW)]
        bench.anki_sync.release_rows.assert_called_once_with((ORPHAN,), NOW)
        assert bench.decisions.forget.call_count == 2  # noqa: PLR2004 — both words

    def test_the_removal_waits_for_a_busy_source(self) -> None:
        bench, acting, _ = self._bench()
        bench.lock.held.side_effect = lambda source_id: (
            SourceOperationKind.UPDATE if source_id == 2 else None  # noqa: PLR2004
        )

        with pytest.raises(SourceOperationBusyError):
            bench.press(acting, Press.KNOWN)

        bench.known.remove_known.assert_not_called()

    def test_a_removal_from_a_report_reaches_every_word(self) -> None:
        bench, acting, other = self._bench()
        before = bench.vocabulary.of(LEMMA)

        bench.effects.known_removed(LEMMA, before)

        saved = {c.args[0].word_id for c in bench.words.save.call_args_list}
        assert saved == {acting.word_id, other.word_id}
