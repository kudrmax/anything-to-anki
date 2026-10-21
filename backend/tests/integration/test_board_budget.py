"""Time budget of the sources board over a book: light projections of shown phrases."""
from __future__ import annotations

import gc
import statistics
import time
from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.source_scope import SourceScope
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.models import SourceModel, dump_phrase
from sqlalchemy import text

from tests.decision_support import project_words
from tests.phrase_support import phrase
from tests.word_support import TEST_SECTION

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

BOOK_WORDS = 4_000
BOOK_PHRASES = 12_800
BOARD_BUDGET_S = 0.3
# The median of several timed runs: one run may catch a CPU spike.
TIMED_RUNS = 5
SOURCE = 1
CREATED_AT = "2026-01-01 00:00:00"
TEXT = "The quick brown {lemma} jumps over the lazy dog while a zephyr hums near the river bank"


def _seed_book(session: Session) -> None:
    session.add(SourceModel(id=SOURCE, title="Book", status="done"))
    session.flush()
    session.execute(
        text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency, is_sweet_spot,"
            " occurrences, is_phrasal_verb)"
            " VALUES (:id, 1, :lemma, 'NOUN', 3.0, 0, 3, 0)"
        ),
        [{"id": i, "lemma": f"lemma{i}"} for i in range(1, BOOK_WORDS + 1)],
    )
    rows = []
    for phrase_id in range(1, BOOK_PHRASES + 1):
        word_id = (phrase_id - 1) % BOOK_WORDS + 1
        lemma = f"lemma{word_id}"
        rows.append({
            "id": phrase_id,
            "word": word_id,
            "phrase": dump_phrase(phrase(TEXT.format(lemma=lemma), lemma, new=["zephyr"])),
            "shown": "selection" if phrase_id <= BOOK_WORDS else None,
            "choice": "learn" if word_id % 10 == 0 and phrase_id <= BOOK_WORDS else "none",
            "section": TEST_SECTION,
        })
    session.execute(
        text(
            "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by, choice,"
            " created_at, earned_section)"
            " VALUES (:id, :word, :phrase, 'auto', :shown, :choice, '2026-01-01', :section)"
        ),
        rows,
    )
    project_words(session)
    session.commit()


def test_the_board_of_a_book_fits_the_budget(db_session: Session) -> None:
    _seed_book(db_session)
    use_case = Container().get_sources_use_case(db_session)
    use_case.board(SourceScope.parse("all"))

    timings = []
    gc.collect()
    gc.disable()  # a collection inside a timed run is not the board's cost
    try:
        for _ in range(TIMED_RUNS):
            started = time.perf_counter()
            board = use_case.board(SourceScope.parse("all"))
            timings.append(time.perf_counter() - started)
    finally:
        gc.enable()
    elapsed = statistics.median(timings)

    [summary] = [s for g in board.groups for s in g.sources]
    assert summary.candidate_count == BOOK_WORDS
    assert summary.learn_count == BOOK_WORDS // 10
    print(f"board of a {BOOK_WORDS}-word / {BOOK_PHRASES}-phrase book: {elapsed * 1000:.0f} ms")
    assert elapsed < BOARD_BUDGET_S
