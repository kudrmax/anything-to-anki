"""The 30-day timer and what a lemma's knowledge reads as."""
from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER_DAYS, timer_due
from backend.domain.value_objects.lemma_knowledge import STANDING, LemmaKnowledge

EXPORTED = datetime(2026, 9, 1, 12, tzinfo=UTC)
NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)
DUE = NOW - timedelta(days=LEARNING_KNOWN_AFTER_DAYS)
FRESH = NOW - timedelta(days=LEARNING_KNOWN_AFTER_DAYS - 1)


def _day(days: int) -> datetime:
    return EXPORTED + timedelta(days=days)


def _knowledge(
    *, known_marked: bool = False, unknown: bool = False, learn_anywhere: bool = False,
    active_since: tuple[datetime, ...] = (),
) -> LemmaKnowledge:
    return LemmaKnowledge.at(
        NOW, known_marked=known_marked, unknown=unknown, learn_anywhere=learn_anywhere,
        active_since=active_since,
    )


@pytest.mark.unit
class TestTimerDue:
    def test_the_timer_is_thirty_days(self) -> None:
        assert LEARNING_KNOWN_AFTER_DAYS == 30

    def test_day_29_is_not_due(self) -> None:
        assert timer_due(EXPORTED, _day(29)) is False

    def test_a_second_before_day_30_is_not_due(self) -> None:
        assert timer_due(EXPORTED, _day(30) - timedelta(seconds=1)) is False

    def test_day_30_is_due(self) -> None:
        assert timer_due(EXPORTED, _day(30)) is True

    def test_later_stays_due(self) -> None:
        assert timer_due(EXPORTED, _day(365)) is True


@pytest.mark.unit
class TestLemmaKnowledge:
    def test_any_due_comes_from_the_active_bindings(self) -> None:
        assert _knowledge(active_since=(FRESH, DUE)).any_due is True
        assert _knowledge(active_since=(FRESH,)).any_due is False
        assert _knowledge().any_due is False

    def test_known_by_the_list(self) -> None:
        knowledge = _knowledge(known_marked=True)
        assert knowledge.is_known is True
        assert knowledge.timer_known is False

    def test_known_by_the_timer(self) -> None:
        knowledge = _knowledge(active_since=(DUE,))
        assert knowledge.is_known is True
        assert knowledge.timer_known is True

    def test_unknown_wins_over_the_known_list(self) -> None:
        """Stage 4's migration removes such conflicts; till then Unknown wins the list."""
        knowledge = _knowledge(known_marked=True, unknown=True)
        assert knowledge.listed_known is False
        assert knowledge.is_known is False
        assert knowledge.elsewhere is None

    def test_unknown_masks_neither_the_timer_nor_a_learn(self) -> None:
        """Spec §1: Unknown never meets a Learn or a note in Anki, so it hides neither."""
        assert _knowledge(unknown=True, active_since=(DUE,)).timer_known is True
        assert _knowledge(unknown=True, active_since=(FRESH,)).is_learning is True
        assert _knowledge(unknown=True, learn_anywhere=True).is_learn is True

    def test_learning_while_the_timer_runs(self) -> None:
        knowledge = _knowledge(learn_anywhere=True, active_since=(FRESH,))
        assert knowledge.is_learning is True
        assert knowledge.is_learn is False

    def test_learn_while_waiting_for_export(self) -> None:
        knowledge = _knowledge(learn_anywhere=True)
        assert knowledge.is_learn is True
        assert knowledge.is_learning is False

    def test_nothing_is_new(self) -> None:
        knowledge = _knowledge()
        assert (knowledge.is_known, knowledge.is_learning, knowledge.is_learn) == (
            False, False, False,
        )

    @pytest.mark.parametrize(
        ("known_marked", "unknown", "learn_anywhere", "active_since"),
        list(itertools.product(
            (False, True), (False, True), (False, True), ((), (FRESH,), (DUE,), (FRESH, DUE)),
        )),
    )
    def test_at_most_one_status_holds(
        self, known_marked: bool, unknown: bool, learn_anywhere: bool,
        active_since: tuple[datetime, ...],
    ) -> None:
        knowledge = _knowledge(
            known_marked=known_marked, unknown=unknown, learn_anywhere=learn_anywhere,
            active_since=active_since,
        )
        assert sum((knowledge.is_known, knowledge.is_learning, knowledge.is_learn)) <= 1

    def test_the_standing_table_holds_the_precedence_known_learning_learn(self) -> None:
        assert set(STANDING) == set(itertools.product((False, True), repeat=3))
        for (known, in_anki, waiting), standing in STANDING.items():
            expected = (
                ElsewhereStatus.KNOWN if known
                else ElsewhereStatus.LEARNING if in_anki
                else ElsewhereStatus.LEARN if waiting
                else None
            )
            assert standing is expected

    @pytest.mark.parametrize(
        ("known_marked", "unknown", "learn_anywhere", "active_since"),
        list(itertools.product(
            (False, True), (False, True), (False, True), ((), (FRESH,), (DUE,)),
        )),
    )
    def test_the_statuses_read_the_standing(
        self, known_marked: bool, unknown: bool, learn_anywhere: bool,
        active_since: tuple[datetime, ...],
    ) -> None:
        knowledge = _knowledge(
            known_marked=known_marked, unknown=unknown, learn_anywhere=learn_anywhere,
            active_since=active_since,
        )
        assert (knowledge.is_known, knowledge.is_learning, knowledge.is_learn) == (
            knowledge.elsewhere is ElsewhereStatus.KNOWN,
            knowledge.elsewhere is ElsewhereStatus.LEARNING,
            knowledge.elsewhere is ElsewhereStatus.LEARN,
        )
