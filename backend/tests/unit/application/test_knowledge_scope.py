"""The knowledge scope: one `now` and one snapshot per request, read anew after a write."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from backend.application.utils.knowledge_scope import KnowledgeScope
from backend.application.utils.user_vocabulary import UserVocabulary
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER

from tests.decision_support import NOW, FixedClock

pytestmark = pytest.mark.unit

DUE = NOW - LEARNING_KNOWN_AFTER
FRESH = NOW - timedelta(days=1)


class Bench:
    def __init__(self) -> None:
        self.clock = FixedClock()
        self.marks = MagicMock()
        self.marks.known_lemmas.return_value = set()
        self.marks.unknown_lemmas.return_value = set()
        self.learning = MagicMock()
        self.learning.awaiting_export.return_value = frozenset()
        self.learning.active_since.return_value = {}
        self.scope = KnowledgeScope(self.clock, self.marks, self.learning)
        self.vocabulary = UserVocabulary(self.marks, self.scope)


@pytest.fixture
def bench() -> Bench:
    return Bench()


def test_one_request_reads_one_now(bench: Bench) -> None:
    first = bench.scope.now
    bench.clock.moment = NOW + timedelta(days=40)

    assert bench.scope.now == first
    bench.vocabulary.mark_known("glare", "VERB")
    assert bench.scope.now == first
    assert bench.clock.reads == 1


def test_reads_share_one_snapshot(bench: Bench) -> None:
    bench.vocabulary.is_known("glare")
    bench.vocabulary.snapshot()
    bench.vocabulary.known_count()

    bench.marks.known_lemmas.assert_called_once()
    bench.learning.active_since.assert_called_once()


@pytest.mark.parametrize(
    "write",
    [
        lambda v: v.mark_known("glare", "VERB"),
        lambda v: v.mark_unknown("glare"),
        lambda v: v.forget_every_pos("glare"),
        lambda v: v.remove_known_entry("glare", "VERB"),
        lambda v: v.forget_unknown("glare"),
    ],
)
def test_a_write_in_the_scope_rebuilds_the_snapshot(bench: Bench, write: object) -> None:
    assert not bench.vocabulary.is_known("glare")
    bench.marks.known_lemmas.return_value = {"glare"}

    write(bench.vocabulary)  # type: ignore[operator]

    assert bench.vocabulary.is_known("glare")
    assert bench.marks.known_lemmas.call_count == 2  # noqa: PLR2004 — before and after


def test_a_binding_write_is_seen_after_invalidate(bench: Bench) -> None:
    assert not bench.vocabulary.snapshot().is_learning("glare")
    bench.learning.active_since.return_value = {"glare": (FRESH,)}

    bench.scope.invalidate()

    assert bench.vocabulary.snapshot().is_learning("glare")


def test_known_count_counts_a_lemma_with_two_pos_once(bench: Bench) -> None:
    bench.marks.known_lemmas.return_value = {"glare"}

    assert bench.vocabulary.known_count() == 1


def test_known_count_and_the_vocabulary_include_a_lemma_known_by_its_timer(
    bench: Bench,
) -> None:
    bench.marks.known_lemmas.return_value = {"linger"}
    bench.learning.active_since.return_value = {"glare": (DUE,), "wander": (FRESH,)}

    assert bench.vocabulary.known_count() == 2  # noqa: PLR2004 — linger, glare
    vocabulary = bench.vocabulary.snapshot()
    assert vocabulary.is_known("glare")
    assert vocabulary.is_learning("wander")
    knowledge = bench.vocabulary.of("glare")
    assert (knowledge.timer_known, knowledge.known_marked) == (True, False)


def test_a_learn_waiting_for_export_is_learning(bench: Bench) -> None:
    bench.learning.awaiting_export.return_value = frozenset({"glare"})

    assert bench.vocabulary.snapshot().is_learning("glare")
    assert bench.vocabulary.of("glare").is_learn
