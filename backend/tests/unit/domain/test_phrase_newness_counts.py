"""The counts of new words at every threshold step, read in one pass, equal the count at
each step on its own."""
from __future__ import annotations

import random

import pytest
from backend.domain.value_objects.frequent_word_threshold import THRESHOLD_STEPS
from backend.domain.value_objects.phrase_newness import PhraseNewness
from backend.domain.value_objects.user_knowledge import Newness

pytestmark = pytest.mark.unit

LEMMAS = ("gleam", "Gleam", "spark", "dwell", "the")
ZIPFS = (1.0, 2.5, 2.9, 3.0, 3.49, 3.5, 4.2, 5.5, 6.1)
PHRASES = 500
LONGEST = 9


def _each_step(newness: PhraseNewness) -> tuple[int, ...]:
    return tuple(newness.count(step) for step in THRESHOLD_STEPS)


@pytest.mark.parametrize("seed", range(4))
def test_one_pass_counts_equal_the_count_at_each_step(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(PHRASES):
        newness = PhraseNewness.of(
            (rng.choice(LEMMAS), rng.choice(ZIPFS), rng.choice(list(Newness)))
            for _ in range(rng.randrange(LONGEST))
        )
        assert newness.counts(THRESHOLD_STEPS) == _each_step(newness)


def test_a_lemma_always_new_counts_once_whatever_its_rare_words() -> None:
    newness = PhraseNewness.of([
        ("gleam", 5.0, Newness.IF_RARE), ("gleam", 2.0, Newness.ALWAYS),
        ("spark", 4.0, Newness.IF_RARE), ("spark", 2.8, Newness.IF_RARE),
        ("dwell", 1.0, Newness.NEVER),
    ])
    assert newness.counts(THRESHOLD_STEPS) == (1, 2, 2, 2, 2, 2, 2, 2)
    assert newness.counts(THRESHOLD_STEPS) == _each_step(newness)


def test_two_spellings_of_a_lemma_count_apart() -> None:
    newness = PhraseNewness.of([("Gleam", 2.0, Newness.ALWAYS), ("gleam", 2.0, Newness.ALWAYS)])
    assert newness.counts(THRESHOLD_STEPS) == _each_step(newness) == (2,) * len(THRESHOLD_STEPS)
