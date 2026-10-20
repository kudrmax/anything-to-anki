"""A card's choice and binding, and the word status every reader sees."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from backend.domain.exceptions import PhraseNotFoundError
from backend.domain.value_objects.card_choice import (
    Binding,
    CardChoice,
    CardState,
    DecisionStatus,
    NoteKind,
    Refusal,
    WordState,
    chosen_status,
    decision_status,
    export_kind,
    in_anki,
    reads_known,
    status_of,
)
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER_DAYS
from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge
from backend.domain.value_objects.word_status import WordStatus

NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)
DUE = NOW - timedelta(days=LEARNING_KNOWN_AFTER_DAYS)
FRESH = NOW - timedelta(days=LEARNING_KNOWN_AFTER_DAYS - 1)


def _word(*cards: CardState) -> WordState:
    return WordState(word_id=1, lemma="procrastinate", pos="verb", source_id=1, cards=cards)


def _knowledge(
    *, known_marked: bool = False, unknown: bool = False, active_since: tuple[datetime, ...] = (),
) -> LemmaKnowledge:
    return LemmaKnowledge.at(
        NOW, known_marked=known_marked, unknown=unknown, learn_anywhere=False,
        active_since=active_since,
    )


def _bound(choice: CardChoice, kind: NoteKind, since: datetime = FRESH) -> CardState:
    return CardState(1, choice, Binding(kind, since))


@pytest.mark.unit
class TestTypes:
    def test_the_seen_status_has_learning(self) -> None:
        assert [s.name for s in WordStatus] == ["NEW", "LEARN", "LEARNING", "KNOWN"]

    def test_the_stored_status_mirrors_the_seen_one(self) -> None:
        assert [(s.name, s.value) for s in DecisionStatus] == [
            (s.name, s.value) for s in WordStatus
        ]

    def test_learn_before_export_counts_elsewhere(self) -> None:
        assert {s.name for s in ElsewhereStatus} == {"KNOWN", "LEARNING", "LEARN"}

    def test_there_is_no_in_anki_refusal(self) -> None:
        assert {r.name for r in Refusal} == {"NOT_DECISION_CARD", "DECIDED_ELSEWHERE"}


@pytest.mark.unit
class TestCardFacts:
    def test_in_anki_is_an_active_binding(self) -> None:
        assert in_anki(_bound(CardChoice.LEARN, NoteKind.LEARN)) is True
        assert in_anki(CardState(1, CardChoice.LEARN)) is False

    @pytest.mark.parametrize(
        ("choice", "kind"),
        [
            (CardChoice.LEARN, NoteKind.LEARN),
            (CardChoice.CLOZE, NoteKind.CLOZE),
            (CardChoice.KNOWN, None),
            (CardChoice.SKIP, None),
            (CardChoice.NONE, None),
        ],
    )
    def test_export_kind_follows_the_choice(
        self, choice: CardChoice, kind: NoteKind | None,
    ) -> None:
        assert export_kind(CardState(1, choice)) is kind

    def test_a_missing_card_is_not_found(self) -> None:
        with pytest.raises(PhraseNotFoundError):
            _word(CardState(1, CardChoice.NONE)).card(2)

    def test_no_decision_reads_as_none_without_a_card(self) -> None:
        word = _word(CardState(1, CardChoice.SKIP))
        assert word.decision_card is None
        assert (word.decision_choice, word.decision_note) == (CardChoice.NONE, None)

    def test_the_decision_facts_come_from_the_decision_card(self) -> None:
        word = _word(CardState(1, CardChoice.SKIP), _bound(CardChoice.CLOZE, NoteKind.CLOZE))
        assert (word.decision_choice, word.decision_note) == (CardChoice.CLOZE, NoteKind.CLOZE)

    def test_with_cards_replaces_in_place_and_appends(self) -> None:
        word = _word(CardState(1, CardChoice.LEARN), CardState(2, CardChoice.SKIP))
        changed = word.with_cards(CardState(1, CardChoice.NONE), CardState(9, CardChoice.KNOWN))
        assert changed.cards == (
            CardState(1, CardChoice.NONE), CardState(2, CardChoice.SKIP),
            CardState(9, CardChoice.KNOWN),
        )


@pytest.mark.unit
class TestDecisionStatus:
    @pytest.mark.parametrize(
        ("cards", "status"),
        [
            ((), DecisionStatus.NEW),
            ((CardState(1, CardChoice.NONE), CardState(2, CardChoice.SKIP)), DecisionStatus.NEW),
            ((CardState(1, CardChoice.KNOWN),), DecisionStatus.KNOWN),
            ((_bound(CardChoice.KNOWN, NoteKind.LEARN),), DecisionStatus.KNOWN),
            ((CardState(1, CardChoice.LEARN),), DecisionStatus.LEARN),
            ((CardState(1, CardChoice.CLOZE),), DecisionStatus.LEARN),
            ((_bound(CardChoice.LEARN, NoteKind.LEARN),), DecisionStatus.LEARNING),
            ((_bound(CardChoice.CLOZE, NoteKind.CLOZE),), DecisionStatus.LEARNING),
        ],
    )
    def test_decision_status_has_no_time_in_it(
        self, cards: tuple[CardState, ...], status: DecisionStatus,
    ) -> None:
        assert decision_status(_word(*cards)) is status


@pytest.mark.unit
class TestReadsKnown:
    def test_a_learning_card_reads_known_by_the_list(self) -> None:
        card = _bound(CardChoice.LEARN, NoteKind.LEARN)
        assert reads_known(card, _knowledge(known_marked=True), NOW) is True

    def test_a_learning_card_reads_known_by_its_timer(self) -> None:
        card = _bound(CardChoice.CLOZE, NoteKind.CLOZE, DUE)
        assert reads_known(card, _knowledge(active_since=(DUE,)), NOW) is True

    def test_the_timer_is_the_cards_own_binding_date(self) -> None:
        card = _bound(CardChoice.LEARN, NoteKind.LEARN, FRESH)
        older_row_of_the_note = _knowledge(active_since=(DUE, FRESH))
        assert older_row_of_the_note.any_due is True
        assert reads_known(card, older_row_of_the_note, NOW) is False

    @pytest.mark.parametrize(
        "card",
        [
            CardState(1, CardChoice.KNOWN),
            CardState(1, CardChoice.SKIP),
            _bound(CardChoice.KNOWN, NoteKind.LEARN, DUE),
        ],
    )
    def test_only_a_learn_or_cloze_card_reads_known(self, card: CardState) -> None:
        assert reads_known(card, _knowledge(known_marked=True, active_since=(DUE,)), NOW) is False

    @pytest.mark.parametrize("choice", [CardChoice.LEARN, CardChoice.CLOZE])
    def test_a_learn_not_exported_reads_known_by_the_list(self, choice: CardChoice) -> None:
        """Q15: the lemma was put in Known after the Learn; the later action wins."""
        assert reads_known(CardState(1, choice), _knowledge(known_marked=True), NOW) is True

    def test_a_learn_not_exported_has_no_timer(self) -> None:
        card = CardState(1, CardChoice.LEARN)
        assert reads_known(card, _knowledge(active_since=(DUE,)), NOW) is False


@pytest.mark.unit
class TestStatusOf:
    def test_learning_that_reads_known_is_known(self) -> None:
        word = _word(_bound(CardChoice.LEARN, NoteKind.LEARN, DUE))
        assert status_of(word, _knowledge(active_since=(DUE,)), NOW) is WordStatus.KNOWN

    def test_learning_on_day_29_is_learning(self) -> None:
        word = _word(_bound(CardChoice.LEARN, NoteKind.LEARN, FRESH))
        assert status_of(word, _knowledge(active_since=(FRESH,)), NOW) is WordStatus.LEARNING

    def test_learn_before_export_stays_learn(self) -> None:
        word = _word(CardState(1, CardChoice.LEARN))
        assert status_of(word, _knowledge(active_since=(DUE,)), NOW) is WordStatus.LEARN

    def test_learn_before_export_reads_known_once_its_lemma_is_known(self) -> None:
        """Q15."""
        word = _word(CardState(1, CardChoice.LEARN))
        assert status_of(word, _knowledge(known_marked=True), NOW) is WordStatus.KNOWN

    def test_the_chosen_status_ignores_the_lists(self) -> None:
        word = _word(CardState(1, CardChoice.LEARN))
        assert chosen_status(word) is WordStatus.LEARN
        assert chosen_status(_word(_bound(CardChoice.LEARN, NoteKind.LEARN, DUE))) is (
            WordStatus.LEARNING
        )

    def test_no_decision_is_new(self) -> None:
        word = _word(CardState(1, CardChoice.SKIP))
        assert status_of(word, _knowledge(known_marked=True), NOW) is WordStatus.NEW

    def test_a_known_choice_is_known(self) -> None:
        word = _word(CardState(1, CardChoice.KNOWN))
        assert status_of(word, _knowledge(known_marked=True), NOW) is WordStatus.KNOWN
