"""Processing a new source is a rebuild of an empty one: every occurrence becomes a phrase
and selection shows the best one of each word."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.exceptions import SourceOperationBusyError
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.phrase_origin_kind import ShownBy
from backend.domain.value_objects.source_operation_kind import SourceOperationKind

from tests.source_rebuild_support import LINES, SOURCE, Bench, at, time_of_line, word

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest.fixture
def bench(db_session: Session) -> Bench:
    return Bench(db_session)


def test_every_occurrence_becomes_an_auto_phrase_with_its_key_and_score(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 5.0), at(1, 2.0), at(5, 2.0)))

    phrases = bench.phrases()
    assert [(p.block, p.line, p.char) for p in phrases] == [(0, 0, 0), (0, 1, 0), (0, 5, 0)]
    assert [p.fragment_score for p in phrases] == [5.0, 2.0, 2.0]
    assert {p.origin for p in phrases} == {"auto"}
    assert [OccurrenceRow.hash_text(LINES[line]) for line in (0, 1, 5)] == [
        row.text_hash for row in bench.occurrences.projection(SOURCE)
    ]


def test_selection_shows_the_best_phrase_ties_to_the_first(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 5.0), at(1, 2.0), at(5, 2.0)))

    assert [p.shown_by for p in bench.phrases()] == [None, ShownBy.SELECTION.value, None]


def test_the_card_of_a_word_is_its_selection_phrase(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 5.0), at(1, 2.0)), word("linger", at(3), at(4, 0.1)))

    cards = {c.lemma: c for c in bench.candidates.get_by_source(SOURCE)}

    assert set(cards) == {"glare", "linger"}
    assert cards["glare"].source_phrase.text == LINES[1]
    assert cards["linger"].source_phrase.text == LINES[4]
    assert cards["glare"].occurrences == 2


def test_processing_marks_the_source_done_and_frees_it(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))

    assert bench.status() == "done"
    assert bench.lock.held(SOURCE) is None


def test_processing_takes_the_source(bench: Bench) -> None:
    bench.process().start(SOURCE)

    assert bench.lock.held(SOURCE) is SourceOperationKind.PROCESS
    assert bench.status() == "processing"
    with pytest.raises(SourceOperationBusyError):
        bench.rebuild().execute(SOURCE, include_open=False)


def test_a_failed_processing_frees_the_source(bench: Bench) -> None:
    process = bench.process()
    process.start(SOURCE)
    bench.session.commit()
    bench.analyze_text.execute.side_effect = RuntimeError("parser crashed")

    with pytest.raises(RuntimeError):
        process.execute(SOURCE)

    assert bench.lock.held(SOURCE) is None
    assert bench.phrases() == []


def test_usage_and_the_analysis_settings_reach_the_word(bench: Bench) -> None:
    glare = word("glare", at(0))
    glare.usage_distribution = {"informal": 1.0}
    bench.processed(glare)

    [card] = bench.candidates.get_by_source(SOURCE)
    assert card.usage_distribution is not None
    assert card.usage_distribution.groups == {"informal": 1.0}
    _document, request = bench.analyze_text.execute.call_args[0]
    assert request.user_level == "B1"


def test_every_phrase_of_a_video_gets_the_time_of_its_line(db_session: Session) -> None:
    video = Bench(db_session, timed=True)

    video.processed(word("glare", at(0), at(2)), word("linger", at(3)))

    for lemma, line in (("glare", 0), ("glare", 2), ("linger", 3)):
        assert video.times(video.phrase_on(lemma, line).id) == time_of_line(line)


def test_phrases_of_a_text_get_no_media(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))

    assert bench.times(bench.phrase_on("glare", 0).id) is None
