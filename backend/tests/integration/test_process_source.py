"""Processing a new source is a rebuild of an empty one: every occurrence becomes a phrase
and selection shows the best one of each word."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.phrase_origin_kind import ShownBy
from sqlalchemy import text

from tests.source_rebuild_support import (
    LINES,
    SOURCE,
    Bench,
    SharedBench,
    at,
    time_of_line,
    word,
)

if TYPE_CHECKING:
    from pathlib import Path

    from backend.domain.entities.stored_candidate import StoredCandidate
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

SECOND = SOURCE + 1


@pytest.fixture
def bench(db_session: Session) -> Bench:
    return Bench(db_session)


def test_the_analysis_holds_no_write_and_shows_nothing_before_it_is_applied(
    tmp_path: Path,
) -> None:
    shared = SharedBench(tmp_path)
    try:
        shared.bench.processed(word("glare", at(0)))

        assert (shared.free, shared.phrases_seen) == ([True], [0])
        assert shared.phrases_elsewhere() == 1
    finally:
        shared.close()


def test_every_occurrence_becomes_an_auto_phrase_with_its_key_and_score(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 500.0), at(1, 200.0), at(5, 200.0)))

    phrases = bench.phrases()
    assert [(p.block, p.line, p.char) for p in phrases] == [(0, 0, 0), (0, 1, 0), (0, 5, 0)]
    assert [p.fragment_score for p in phrases] == [500.0, 200.0, 200.0]
    assert {p.origin for p in phrases} == {"auto"}
    assert [OccurrenceRow.hash_text(LINES[line]) for line in (0, 1, 5)] == [
        row.text_hash for row in bench.occurrences.projection(SOURCE)
    ]


def test_selection_shows_the_best_phrase_ties_to_the_first(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 500.0), at(1, 200.0), at(5, 200.0)))

    assert [p.shown_by for p in bench.phrases()] == [None, ShownBy.SELECTION.value, None]


def test_the_card_of_a_word_is_its_selection_phrase(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 500.0), at(1, 200.0)), word("linger", at(3), at(4, 10.0)))

    words = {w.lemma: w for w in bench.candidates.get_by_source(SOURCE)}
    shown = bench.occurrences.shown_by_word(SOURCE)

    assert set(words) == {"glare", "linger"}
    assert [o.source_phrase.text for o in shown[_id(words["glare"])]] == [LINES[1]]
    assert [o.source_phrase.text for o in shown[_id(words["linger"])]] == [LINES[4]]
    assert words["glare"].occurrences == 2


def _id(word: StoredCandidate) -> int:
    assert word.id is not None
    return word.id


def test_processing_marks_the_source_done(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))

    assert bench.status() == "done"
    assert bench.lock.held(SOURCE) is None


def test_sources_are_processed_together_and_one_that_fails_shows_its_error(
    bench: Bench,
) -> None:
    bench.session.execute(text(
        "INSERT INTO sources (id, title, status, role, created_at)"
        f" VALUES ({SECOND}, 'title', 'new', 'content', '2026-01-02 00:00:00')"
    ))
    bench.session.commit()
    bench.analysis = [word("glare", at(0))]

    result = bench.process().run([SOURCE, SECOND])

    assert result is not None
    assert result.failed == 1
    assert bench.status() == "done"
    bench.session.expire_all()
    status, error = bench.session.execute(text(
        f"SELECT status, error_message FROM sources WHERE id = {SECOND}"
    )).one()
    assert status == "error"
    assert f"Source {SECOND} has no document" in error


def test_a_failure_while_applying_writes_nothing(bench: Bench) -> None:
    bench.analysis = [word("glare", at(0))]
    process = bench.process()
    bench.occurrences.apply_plan = MagicMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("disk full"),
    )

    with pytest.raises(RuntimeError, match="disk full"):
        process.run([SOURCE])

    assert bench.status() == "new"
    assert bench.phrases() == []


def test_usage_and_the_analysis_settings_reach_the_word(bench: Bench) -> None:
    glare = word("glare", at(0))
    glare.usage_distribution = {"informal": 1.0}
    bench.processed(glare)

    [card] = bench.candidates.get_by_source(SOURCE)
    assert card.usage_distribution is not None
    assert card.usage_distribution.groups == {"informal": 1.0}
    _document, request, _report = bench.analyze_text.execute.call_args[0]
    assert request.user_level == "B1"


def test_every_phrase_of_a_video_gets_the_time_of_its_line(db_session: Session) -> None:
    video = Bench(db_session, timed=True)

    video.processed(word("glare", at(0), at(2)), word("linger", at(3)))

    for lemma, line in (("glare", 0), ("glare", 2), ("linger", 3)):
        assert video.times(video.phrase_on(lemma, line).id) == time_of_line(line)


def test_phrases_of_a_text_get_no_media(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))

    assert bench.times(bench.phrase_on("glare", 0).id) is None
