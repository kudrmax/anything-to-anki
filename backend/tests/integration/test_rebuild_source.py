"""Rebuild: a fresh analysis applied to a source without losing the user's work."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.job import Job
from backend.domain.exceptions import (
    RebuildNotSupportedError,
    SourceNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.value_objects.card_choice import CardChoice
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import JobModel
from sqlalchemy import select, text

from tests.rebuild_support import text_phrase
from tests.source_rebuild_support import (
    LINES,
    SOURCE,
    Bench,
    at,
    time_of_line,
    word,
)
from tests.vocabulary_support import user_vocabulary
from tests.word_support import bind

if TYPE_CHECKING:
    from backend.application.dto.analysis_dtos import AnalyzeTextRequest
    from backend.domain.value_objects.document import Document
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

CHANGED = "He glared at me, again."


@pytest.fixture
def bench(db_session: Session) -> Bench:
    return Bench(db_session)


@pytest.fixture
def video(db_session: Session) -> Bench:
    return Bench(db_session, timed=True)


# ── decisions and generation survive ──────────────────────────────────


def test_a_decided_word_the_analysis_lost_keeps_its_card(bench: Bench) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    decision = bench.phrase_on("linger", 3)
    bench.decide_learn("linger", decision.id)
    bench.analysis = [word("glare", at(0))]

    summary = bench.rebuild().execute(SOURCE, include_open=True)

    assert summary.counts.words_removed == 0
    [linger] = [w for w in bench.occurrences.word_rows(SOURCE) if w.lemma == "linger"]
    assert linger.status is WordStatus.LEARN
    kept = bench.occurrences.get(decision.id)
    assert kept is not None
    assert kept.choice is CardChoice.LEARN
    assert bench.shown_lines("linger") == [3]


def test_the_analysis_takes_words_learned_elsewhere_but_not_here_out(bench: Bench) -> None:
    """A word learned in another source is no new candidate; one learned here stays one."""
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    bench.decide_learn("linger", bench.phrase_on("linger", 3).id)
    bench.vocabulary = user_vocabulary(learning_lemmas={"glare", "linger", "wander"})

    bench.rebuild().execute(SOURCE, include_open=False)

    request: AnalyzeTextRequest = bench.analyze_text.execute.call_args.args[1]
    assert request.vocabulary.learning == {"glare", "wander"}


def test_a_word_exported_from_here_stays_a_candidate(bench: Bench) -> None:
    """Chosen to learn here, in Anki or not: Learning words stay this source's candidates."""
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    linger = bench.phrase_on("linger", 3)
    bench.decide_learn("linger", linger.id)
    bind(bench.session, linger.candidate_id, linger.id)
    bench.session.commit()
    bench.vocabulary = user_vocabulary(learning_lemmas={"linger", "wander"})

    bench.rebuild().execute(SOURCE, include_open=False)

    request: AnalyzeTextRequest = bench.analyze_text.execute.call_args.args[1]
    assert request.vocabulary.learning == {"wander"}
    [kept] = [w for w in bench.occurrences.word_rows(SOURCE) if w.lemma == "linger"]
    assert kept.status is WordStatus.LEARNING


def test_a_word_lost_without_a_decision_goes(bench: Bench) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    bench.analysis = [word("glare", at(0))]

    summary = bench.rebuild().execute(SOURCE, include_open=False)

    assert summary.counts.words_removed == 1
    assert [w.lemma for w in bench.occurrences.word_rows(SOURCE)] == ["glare"]


def test_a_generated_phrase_keeps_the_selection_unless_include_open(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 0.5)))
    generated = bench.phrase_on("glare", 0)
    bench.give_meaning(generated.id)
    bench.analysis = [word("glare", at(0, 0.5), at(2, 0.1))]

    kept = bench.rebuild().execute(SOURCE, include_open=False)

    assert bench.shown_lines("glare") == [0]
    assert kept.counts.cards_new_phrase == 0

    moved = bench.rebuild().execute(SOURCE, include_open=True)

    assert bench.shown_lines("glare") == [2]
    assert moved.counts.cards_new_phrase == 1
    old = bench.occurrences.get(generated.id)
    assert old is not None
    assert old.meaning is not None


def test_a_decision_made_during_the_analysis_is_kept(bench: Bench) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    decision = bench.phrase_on("linger", 3)
    bench.analysis = [word("glare", at(0))]

    analyse = bench.analyze_text.execute.side_effect

    def decide_meanwhile(document: Document, request: AnalyzeTextRequest) -> object:
        bench.decide_learn("linger", decision.id)
        return analyse(document, request)

    bench.analyze_text.execute.side_effect = decide_meanwhile

    bench.rebuild().execute(SOURCE, include_open=True)

    assert "linger" in {w.lemma for w in bench.occurrences.word_rows(SOURCE)}
    assert bench.occurrences.get(decision.id) is not None


def test_a_phrase_with_a_running_job_stays(bench: Bench) -> None:
    bench.processed(word("glare", at(0), at(1)))
    working = bench.phrase_on("glare", 1)
    _running_job(bench, working.id, working.candidate_id)
    bench.analysis = [word("glare", at(0))]

    bench.rebuild().execute(SOURCE, include_open=False)

    assert bench.occurrences.get(working.id) is not None
    assert _active_jobs(bench) == [working.id]


def test_jobs_of_a_reset_phrase_are_cancelled(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    phrase = bench.phrase_on("glare", 0)
    bench.give_meaning(phrase.id)
    _running_job(bench, phrase.id, phrase.candidate_id)
    bench.analysis = [word("glare", at(0, text=CHANGED))]

    summary = bench.rebuild().execute(SOURCE, include_open=True)

    assert summary.counts.cards_text_reset == 1
    assert _active_jobs(bench) == []
    reset = bench.occurrences.get(phrase.id)
    assert reset is not None
    assert (reset.meaning, reset.source_phrase.text, reset.revision) == (None, CHANGED, 1)


# ── protection: what the user marked or made survives either way ──────────

PROTECTED = {  # the card's choice, bound to a note, edited, shown by, origin
    "learn": ("learn", False, False, None, "auto"),
    "cloze": ("cloze", False, False, None, "auto"),
    "known": ("known", False, False, None, "auto"),
    "skip": ("skip", False, False, None, "auto"),
    "in anki": ("learn", True, False, None, "auto"),
    "known in anki": ("known", True, False, None, "auto"),
    "edited": ("none", False, True, None, "auto"),
    "picked by the user": ("none", False, False, "user", "auto"),
    "manual": ("none", False, False, "user", "manual"),
}


def _protect(bench: Bench, phrase_id: int, word_id: int, kind: str) -> None:
    """Only the card changes: the word's stored status stays as processing left it, since
    the rebuild reads the decision from the cards."""
    choice, bound, edited, shown_by, origin = PROTECTED[kind]
    bench.session.execute(
        text(
            "UPDATE phrases SET choice = :choice, edited_by_user = :edited,"
            " shown_by = COALESCE(:shown_by, shown_by), origin = :origin WHERE id = :id"
        ),
        {
            "choice": choice, "edited": edited, "shown_by": shown_by, "origin": origin,
            "id": phrase_id,
        },
    )
    if bound:
        bind(bench.session, word_id, phrase_id)
    bench.session.commit()


def _store_status(bench: Bench, word_id: int, status: str) -> None:
    bench.session.execute(
        text("UPDATE candidates SET status = :status WHERE id = :id"),
        {"status": status, "id": word_id},
    )
    bench.session.commit()


def test_a_results_only_card_keeps_its_text_without_include_open(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    phrase = bench.phrase_on("glare", 0)
    bench.give_meaning(phrase.id)
    bench.analysis = [word("glare", at(0, text=CHANGED))]

    summary = bench.rebuild().execute(SOURCE, include_open=False)

    assert summary.counts.cards_text_reset == 0
    kept = bench.occurrences.get(phrase.id)
    assert kept is not None
    assert kept.meaning is not None
    assert (kept.source_phrase.text, kept.revision) == (LINES[0], 0)


def test_the_cards_choice_decides_the_word_not_its_stored_status(bench: Bench) -> None:
    """A Learn card keeps a word stored as new; a word stored as known with no card
    decided goes when the analysis loses it."""
    bench.processed(word("glare", at(0)), word("linger", at(3)), word("wander", at(5)))
    decided = bench.phrase_on("linger", 3)
    bench.set_choice(decided.id, "learn")
    bench.session.commit()
    stale = bench.phrase_on("wander", 5)
    _store_status(bench, stale.candidate_id, "known")
    bench.analysis = [word("glare", at(0))]

    bench.rebuild().execute(SOURCE, include_open=False)

    lemmas = {w.lemma for w in bench.occurrences.word_rows(SOURCE)}
    assert "linger" in lemmas
    assert "wander" not in lemmas
    assert bench.occurrences.get(decided.id) is not None


@pytest.mark.parametrize("include_open", [False, True])
@pytest.mark.parametrize("kind", PROTECTED)
def test_a_protected_card_keeps_its_text_results_and_word(
    bench: Bench, kind: str, include_open: bool,
) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    card = bench.phrase_on("linger", 3)
    bench.give_meaning(card.id)
    _protect(bench, card.id, card.candidate_id, kind)
    bench.analysis = [word("glare", at(0)), word("linger", at(3, text=CHANGED))]

    bench.rebuild().execute(SOURCE, include_open=include_open)

    kept = bench.occurrences.get(card.id)
    assert kept is not None
    assert (kept.source_phrase.text, kept.revision) == (LINES[3], 0)
    assert kept.meaning is not None


@pytest.mark.parametrize("include_open", [False, True])
@pytest.mark.parametrize("kind", PROTECTED)
def test_a_protected_card_the_analysis_lost_stays_with_its_word(
    bench: Bench, kind: str, include_open: bool,
) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    card = bench.phrase_on("linger", 3)
    _protect(bench, card.id, card.candidate_id, kind)
    bench.analysis = [word("glare", at(0))]

    summary = bench.rebuild().execute(SOURCE, include_open=include_open)

    assert bench.occurrences.get(card.id) is not None
    assert "linger" in {w.lemma for w in bench.occurrences.word_rows(SOURCE)}
    assert summary.counts.words_removed == 0


# ── a second rebuild, preview and counts ──────────────────────────────


def test_a_second_rebuild_changes_nothing(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 0.5), at(1, 0.4)), word("linger", at(3)))
    bench.give_meaning(bench.phrase_on("glare", 1).id)
    bench.analysis = [
        word("glare", at(0, 0.5), at(2, 0.1), at(5, 0.3, text="I glared.")),
        word("linger", at(4)),
    ]
    bench.rebuild().execute(SOURCE, include_open=True)
    before = [(p.id, p.line, p.shown_by, p.revision, p.source_phrase) for p in bench.phrases()]

    again = bench.rebuild().execute(SOURCE, include_open=True)
    preview = bench.rebuild().preview(SOURCE)

    assert again.counts.nothing_to_update
    assert preview.without_open.nothing_to_update
    assert preview.with_open.nothing_to_update
    after = [(p.id, p.line, p.shown_by, p.revision, p.source_phrase) for p in bench.phrases()]
    assert after == before


def test_the_summary_counts_what_changed(bench: Bench) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    bench.analysis = [word("glare", at(0)), word("ponder", at(1)), word("muse", at(2))]

    summary = bench.rebuild().execute(SOURCE, include_open=False)

    counts = summary.counts
    assert (counts.words_added, counts.words_removed) == (2, 1)
    assert counts.cards_without_generation == 3
    assert not counts.nothing_to_update
    assert not summary.include_open


def test_the_preview_changes_nothing_and_counts_both_ways(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 0.5)))
    generated = bench.phrase_on("glare", 0)
    bench.give_meaning(generated.id)
    bench.analysis = [word("glare", at(0, 0.5, text=CHANGED), at(2, 0.1))]
    before = [(p.id, p.shown_by, p.source_phrase) for p in bench.phrases()]

    preview = bench.rebuild().preview(SOURCE)

    assert preview.without_open.cards_new_phrase == 0
    assert preview.without_open.cards_text_reset == 0
    assert preview.with_open.cards_new_phrase == 1
    assert preview.with_open.cards_text_reset == 1
    assert [(p.id, p.shown_by, p.source_phrase) for p in bench.phrases()] == before
    assert bench.lock.held(SOURCE) is None


# ── the lock and the sources that cannot be rebuilt ───────────────────


def test_a_busy_source_is_refused(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    bench.lock.acquire(SOURCE, SourceOperationKind.PROCESS)
    bench.session.commit()
    bench.analyze_text.execute.reset_mock()

    with pytest.raises(SourceOperationBusyError):
        bench.rebuild().execute(SOURCE, include_open=False)
    with pytest.raises(SourceOperationBusyError):
        bench.rebuild().preview(SOURCE)

    bench.analyze_text.execute.assert_not_called()
    assert bench.lock.held(SOURCE) is SourceOperationKind.PROCESS


def test_the_lock_is_taken_during_the_analysis_and_released_after(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    held: list[SourceOperationKind | None] = []
    analyse = bench.analyze_text.execute.side_effect

    def watch(document: Document, request: AnalyzeTextRequest) -> object:
        held.append(bench.lock.held(SOURCE))
        return analyse(document, request)

    bench.analyze_text.execute.side_effect = watch

    bench.rebuild().execute(SOURCE, include_open=False)
    bench.rebuild().preview(SOURCE)

    assert held == [SourceOperationKind.REBUILD, SourceOperationKind.PREVIEW]
    assert bench.lock.held(SOURCE) is None


def test_a_failed_rebuild_releases_the_lock_and_writes_nothing(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    before = [(p.id, p.shown_by) for p in bench.phrases()]
    bench.analyze_text.execute.side_effect = RuntimeError("parser crashed")

    with pytest.raises(RuntimeError):
        bench.rebuild().execute(SOURCE, include_open=True)

    assert bench.lock.held(SOURCE) is None
    assert [(p.id, p.shown_by) for p in bench.phrases()] == before


def test_a_source_deleted_during_the_analysis_is_not_written(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    analyse = bench.analyze_text.execute.side_effect

    def delete_meanwhile(document: Document, request: AnalyzeTextRequest) -> object:
        bench.session.execute(text("DELETE FROM sources WHERE id = :id"), {"id": SOURCE})
        bench.session.commit()
        return analyse(document, request)

    bench.analyze_text.execute.side_effect = delete_meanwhile
    bench.analysis = [word("glare", at(0)), word("linger", at(3))]

    with pytest.raises(SourceNotFoundError):
        bench.rebuild().execute(SOURCE, include_open=False)

    assert bench.phrases() == []


@pytest.mark.parametrize("role", ["topic", "saved_phrases"])
def test_a_source_without_its_own_text_is_not_rebuilt(db_session: Session, role: str) -> None:
    bench = Bench(db_session, role=role, status="done")

    with pytest.raises(RebuildNotSupportedError):
        bench.rebuild().execute(SOURCE, include_open=False)
    with pytest.raises(RebuildNotSupportedError):
        bench.rebuild().preview(SOURCE)

    assert bench.lock.held(SOURCE) is None


def test_a_source_never_processed_is_not_rebuilt(db_session: Session) -> None:
    """Rebuild is what the source offers once processed; a new one is processed instead."""
    bench = Bench(db_session, status="new")

    with pytest.raises(RebuildNotSupportedError):
        bench.rebuild().execute(SOURCE, include_open=False)
    with pytest.raises(RebuildNotSupportedError):
        bench.rebuild().preview(SOURCE)

    assert bench.lock.held(SOURCE) is None


# ── source status ─────────────────────────────────────────────────────


def test_a_source_in_error_is_processed_again(db_session: Session) -> None:
    bench = Bench(db_session, status="error")
    bench.analysis = [word("glare", at(0))]

    bench.rebuild().execute(SOURCE, include_open=False)

    assert bench.status() == "done"
    assert bench.shown_lines("glare") == [0]


def test_a_reviewed_source_with_a_new_word_is_partly_reviewed(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    bench.decide_learn("glare", bench.phrase_on("glare", 0).id)
    assert bench.review_status() == "reviewed"
    bench.analysis = [word("glare", at(0)), word("linger", at(3))]

    bench.rebuild().execute(SOURCE, include_open=False)

    assert (bench.status(), bench.review_status()) == ("done", "partially_reviewed")


# ── media timecodes (video sources) ───────────────────────────────────


def test_a_new_phrase_of_a_video_gets_the_time_of_its_line(video: Bench) -> None:
    video.processed(word("glare", at(0)))
    video.analysis = [word("glare", at(0)), word("linger", at(3)), word("ponder", at(4))]

    video.rebuild().execute(SOURCE, include_open=False)

    assert video.times(video.phrase_on("linger", 3).id) == time_of_line(3)
    assert video.times(video.phrase_on("ponder", 4).id) == time_of_line(4)


def test_a_rewritten_phrase_of_a_video_gets_the_time_of_its_new_lines(video: Bench) -> None:
    video.processed(word("glare", at(0)))
    phrase = video.phrase_on("glare", 0)
    assert video.times(phrase.id) == time_of_line(0)
    two_lines = _spanning(0, 1)
    video.analysis = [word("glare", two_lines)]

    video.rebuild().execute(SOURCE, include_open=False)

    assert video.times(phrase.id) == (time_of_line(0)[0], time_of_line(1)[1])


def test_a_reset_phrase_of_a_video_gets_the_time_of_its_new_lines(video: Bench) -> None:
    video.processed(word("glare", at(0)))
    phrase = video.phrase_on("glare", 0)
    video.give_meaning(phrase.id)
    video.analysis = [word("glare", _spanning(0, 1))]

    video.rebuild().execute(SOURCE, include_open=True)

    assert video.times(phrase.id) == (time_of_line(0)[0], time_of_line(1)[1])


def test_a_made_clip_keeps_the_time_it_was_cut_at(video: Bench) -> None:
    video.processed(word("glare", at(0)))
    phrase = video.phrase_on("glare", 0)
    video.give_clip(phrase.id, 10, 20)
    video.analysis = [word("glare", _spanning(0, 1))]

    video.rebuild().execute(SOURCE, include_open=False)

    assert video.times(phrase.id) == (10, 20)


@pytest.mark.parametrize("include_open", [False, True])
def test_a_made_clip_keeps_its_time_when_its_phrase_gets_new_facts(
    video: Bench, include_open: bool,
) -> None:
    video.processed(word("glare", at(0)))
    phrase = video.phrase_on("glare", 0)
    video.give_clip(phrase.id, 10, 20)
    same_text = at(0).model_copy(update={"phrase": text_phrase(LINES[0], variant=True)})
    video.analysis = [word("glare", same_text)]

    summary = video.rebuild().execute(SOURCE, include_open=include_open)

    assert summary.counts.cards_text_reset == 0
    assert video.times(phrase.id) == (10, 20)


# ── helpers ───────────────────────────────────────────────────────────


def _spanning(first: int, last: int) -> object:
    """An occurrence on `first` whose phrase runs to the end of line `last`."""
    from backend.application.dto.analysis_dtos import OccurrenceDTO
    from backend.application.dto.document_dtos import DocumentPositionDTO

    from tests.phrase_support import phrase

    joined = " ".join(LINES[first:last + 1])
    return OccurrenceDTO(
        phrase=phrase(joined),
        phrase_position=DocumentPositionDTO(
            block=0, start_line=first, start_char=0, end_line=last, end_char=len(LINES[last]),
        ),
        key=at(first).key,
        fragment_score=0.5,
    )


def _running_job(bench: Bench, phrase_id: int, word_id: int) -> None:
    [job] = bench.jobs.enqueue([Job.queued(
        JobType.MEANING, SOURCE, word_id, phrase_id=phrase_id, phrase_revision=0,
    )])
    bench.session.execute(
        text("UPDATE jobs SET status = :running WHERE id = :id"),
        {"running": JobStatus.RUNNING.value, "id": job.id},
    )
    bench.session.commit()


def _active_jobs(bench: Bench) -> list[int | None]:
    bench.session.expire_all()
    return list(bench.session.scalars(
        select(JobModel.phrase_id).where(
            JobModel.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
    ))


# ── sections are re-stamped ───────────────────────────────────────────


def _earned(bench: Bench) -> dict[int, str | None]:
    return {p.id: p.earned_section for p in bench.phrases()}


def test_rebuild_writes_the_restamped_sections(bench: Bench) -> None:
    bench.processed(word("glare", at(0), at(1)), word("linger", at(3)))
    open_phrase = bench.phrase_on("glare", 0)
    chosen = bench.phrase_on("linger", 3)
    bench.decide_learn("linger", chosen.id)
    bench.session.execute(
        text("UPDATE phrases SET earned_section = 'extra' WHERE id IN (:a, :b)"),
        {"a": open_phrase.id, "b": chosen.id},
    )
    bench.session.commit()

    bench.rebuild().execute(SOURCE, include_open=False)

    earned = _earned(bench)
    assert earned[open_phrase.id] == "ready"
    assert earned[chosen.id] == "extra"


def test_a_preview_that_only_moves_sections_offers_rebuild(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    bench.session.execute(text("UPDATE phrases SET earned_section = 'extra'"))
    bench.session.commit()

    preview = bench.rebuild().preview(SOURCE)

    assert not preview.without_open.nothing_to_update
    assert preview.without_open.words_added == 0
    assert preview.without_open.cards_new_phrase == 0
