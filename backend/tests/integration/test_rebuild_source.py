"""Rebuild: a fresh analysis applied to a source without losing the user's work."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.domain.entities.job import Job
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    RebuildNotSupportedError,
    SourceHasNoDocumentError,
    SourceNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.services.source_operations import REBUILD_OPERATION
from backend.domain.value_objects.card_choice import CardChoice
from backend.domain.value_objects.held_operation import HeldOperation
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import JobModel
from sqlalchemy import select, text

from tests.phrase_support import phrase
from tests.rebuild_support import text_phrase
from tests.source_rebuild_support import (
    LINES,
    SOURCE,
    Bench,
    SharedBench,
    at,
    time_of_line,
    word,
)
from tests.vocabulary_support import user_vocabulary
from tests.word_support import bind, store_card

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from backend.application.dto.analysis_dtos import AnalyzeTextRequest
    from backend.domain.value_objects.document import Document
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

CHANGED = "He glared at me, again."
UPDATE = RebuildMode.UPDATE
RECUT = RebuildMode.RECUT
MODES = (UPDATE, RECUT)


@pytest.fixture
def bench(db_session: Session) -> Bench:
    return Bench(db_session)


@pytest.fixture
def video(db_session: Session) -> Bench:
    return Bench(db_session, timed=True)


@pytest.fixture
def shared(tmp_path: Path) -> Iterator[SharedBench]:
    shared_bench = SharedBench(tmp_path)
    yield shared_bench
    shared_bench.close()


# ── what other sessions see ───────────────────────────────────────────


@pytest.mark.parametrize("mode", MODES)
def test_others_see_the_source_busy_while_it_is_analysed(
    shared: SharedBench, mode: RebuildMode,
) -> None:
    shared.bench.processed(word("glare", at(0)))
    shared.seen.clear()

    shared.bench.rebuild().execute(SOURCE, mode)

    assert shared.seen == [HeldOperation(REBUILD_OPERATION[mode])]
    assert shared.held_elsewhere() is None


def test_others_see_the_source_busy_while_its_preview_is_analysed(
    shared: SharedBench,
) -> None:
    shared.bench.processed(word("glare", at(0)))
    shared.seen.clear()

    shared.bench.rebuild().preview(SOURCE, UPDATE)

    assert shared.seen == [HeldOperation(SourceOperationKind.PREVIEW)]
    assert shared.held_elsewhere() is None


# ── decisions and generation survive ──────────────────────────────────


def test_a_decided_word_the_analysis_lost_keeps_its_card(bench: Bench) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    decision = bench.phrase_on("linger", 3)
    bench.decide_learn("linger", decision.id)
    bench.analysis = [word("glare", at(0))]

    summary = bench.rebuild().execute(SOURCE, RECUT)

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

    bench.rebuild().execute(SOURCE, UPDATE)

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

    bench.rebuild().execute(SOURCE, UPDATE)

    request: AnalyzeTextRequest = bench.analyze_text.execute.call_args.args[1]
    assert request.vocabulary.learning == {"wander"}
    [kept] = [w for w in bench.occurrences.word_rows(SOURCE) if w.lemma == "linger"]
    assert kept.status is WordStatus.LEARNING


def test_a_word_lost_without_a_decision_goes(bench: Bench) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    bench.analysis = [word("glare", at(0))]

    summary = bench.rebuild().execute(SOURCE, UPDATE)

    assert summary.counts.words_removed == 1
    assert [w.lemma for w in bench.occurrences.word_rows(SOURCE)] == ["glare"]


def test_the_card_moves_to_a_better_phrase_and_the_old_one_keeps_its_meaning(
    bench: Bench,
) -> None:
    bench.processed(word("glare", at(0, 50.0)))
    generated = bench.phrase_on("glare", 0)
    bench.give_meaning(generated.id)
    bench.analysis = [word("glare", at(0, 50.0), at(2, 10.0))]

    moved = bench.rebuild().execute(SOURCE, UPDATE)

    assert bench.shown_lines("glare") == [2]
    assert moved.counts.cards_moved == 1
    old = bench.occurrences.get(generated.id)
    assert old is not None
    assert old.meaning is not None


def test_a_card_whose_word_got_known_goes_with_its_meaning_and_files(bench: Bench) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    known = bench.phrase_on("linger", 3)
    bench.give_meaning(known.id)
    bench.give_clip(known.id, 10, 20)
    bench.analysis = [word("glare", at(0))]

    summary = bench.rebuild().execute(SOURCE, UPDATE)

    assert (summary.counts.words_removed, summary.counts.cards_lost_generation) == (1, 1)
    assert bench.occurrences.get(known.id) is None
    assert bench.media_files.removed == ["/media/1/shot.webp", "/media/1/clip.m4a"]


def test_a_card_of_a_word_known_elsewhere_stays_though_the_analysis_lost_it(
    bench: Bench,
) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    card = bench.phrase_on("linger", 3)
    bench.give_meaning(card.id)
    known = MagicMock()
    known.known_lemmas.return_value = {"linger"}
    bench.vocabulary = user_vocabulary(known)
    bench.analysis = [word("glare", at(0))]

    summary = bench.rebuild().execute(SOURCE, UPDATE)

    assert summary.counts.words_removed == 0
    assert bench.occurrences.get(card.id) is not None
    assert bench.shown_lines("linger") == [3]


def test_a_decision_made_during_the_analysis_is_kept(bench: Bench) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    decision = bench.phrase_on("linger", 3)
    bench.analysis = [word("glare", at(0))]

    analyse = bench.analyze_text.execute.side_effect

    def decide_meanwhile(document: Document, request: AnalyzeTextRequest) -> object:
        bench.decide_learn("linger", decision.id)
        return analyse(document, request)

    bench.analyze_text.execute.side_effect = decide_meanwhile

    bench.rebuild().execute(SOURCE, RECUT)

    assert "linger" in {w.lemma for w in bench.occurrences.word_rows(SOURCE)}
    assert bench.occurrences.get(decision.id) is not None


def test_a_phrase_with_a_running_job_stays(bench: Bench) -> None:
    bench.processed(word("glare", at(0), at(1)))
    working = bench.phrase_on("glare", 1)
    _running_job(bench, working.id, working.candidate_id)
    bench.analysis = [word("glare", at(0))]

    bench.rebuild().execute(SOURCE, UPDATE)

    assert bench.occurrences.get(working.id) is not None
    assert _active_jobs(bench) == [working.id]


def test_a_recut_phrase_keeps_its_meaning_and_loses_what_was_made_of_its_text(
    video: Bench,
) -> None:
    video.processed(word("glare", at(0)))
    phrase = video.phrase_on("glare", 0)
    video.give_meaning(phrase.id)
    video.give_clip(phrase.id, 10, 20)
    video.session.execute(
        text("UPDATE phrases SET polished_phrase = source_phrase, polish_reverted = 1"),
    )
    video.session.commit()
    video.analysis = [word("glare", _spanning(0, 1))]

    summary = video.rebuild().execute(SOURCE, RECUT)

    counts = summary.counts
    assert (counts.cards_recut, counts.cards_recut_lost_text_generation) == (1, 1)
    recut = video.occurrences.get(phrase.id)
    assert recut is not None
    assert recut.meaning is not None
    assert recut.revision == 1
    assert (recut.polished_phrase, recut.polish_reverted) == (None, False)
    assert video.times(phrase.id) == (time_of_line(0)[0], time_of_line(1)[1])
    assert video.media_files.removed == ["/media/1/shot.webp", "/media/1/clip.m4a"]


def test_a_recut_moves_queued_jobs_to_the_new_text_and_cancels_running_ones(
    bench: Bench,
) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    queued = bench.phrase_on("glare", 0)
    running = bench.phrase_on("linger", 3)
    _queued_job(bench, queued.id, queued.candidate_id)
    _running_job(bench, running.id, running.candidate_id)
    bench.analysis = [
        word("glare", at(0, text=CHANGED)), word("linger", at(3, text="We lingered on.")),
    ]

    bench.rebuild().execute(SOURCE, RECUT)

    assert _active_jobs(bench) == [queued.id]
    assert _job_revisions(bench) == [1]


@pytest.mark.parametrize("work", ["meaning", "job"])
def test_an_update_keeps_a_phrase_whose_place_is_gone_while_something_is_made_for_it(
    bench: Bench, work: str,
) -> None:
    bench.processed(word("glare", at(0), at(1)))
    gone = bench.phrase_on("glare", 1)
    if work == "meaning":
        bench.give_meaning(gone.id)
    else:
        _running_job(bench, gone.id, gone.candidate_id)
    bench.analysis = [word("glare", at(0))]

    bench.rebuild().execute(SOURCE, UPDATE)

    assert bench.occurrences.get(gone.id) is not None


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
    """Only the card changes: the rebuild reads the decision from the cards."""
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


def test_an_update_keeps_the_text_of_every_card(bench: Bench) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    generated = bench.phrase_on("glare", 0)
    bench.give_meaning(generated.id)
    plain = bench.phrase_on("linger", 3)
    bench.analysis = [
        word("glare", at(0, text=CHANGED)), word("linger", at(3, text="We lingered on.")),
    ]

    summary = bench.rebuild().execute(SOURCE, UPDATE)

    assert summary.counts.cards_recut == 0
    kept = bench.occurrences.get(generated.id)
    assert kept is not None
    assert kept.meaning is not None
    assert (kept.source_phrase.text, kept.revision) == (LINES[0], 0)
    untouched = bench.occurrences.get(plain.id)
    assert untouched is not None
    assert (untouched.source_phrase.text, untouched.revision) == (LINES[3], 0)


def test_the_cards_choice_decides_whether_a_lost_word_stays(bench: Bench) -> None:
    """A word with a Learn card stays when the analysis loses it; a word with no card
    decided goes."""
    bench.processed(word("glare", at(0)), word("linger", at(3)), word("wander", at(5)))
    decided = bench.phrase_on("linger", 3)
    bench.set_choice(decided.id, "learn")
    bench.session.commit()
    bench.analysis = [word("glare", at(0))]

    bench.rebuild().execute(SOURCE, UPDATE)

    lemmas = {w.lemma for w in bench.occurrences.word_rows(SOURCE)}
    assert "linger" in lemmas
    assert "wander" not in lemmas
    assert bench.occurrences.get(decided.id) is not None


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("kind", PROTECTED)
def test_a_protected_card_keeps_its_text_results_and_word(
    bench: Bench, kind: str, mode: RebuildMode,
) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    card = bench.phrase_on("linger", 3)
    bench.give_meaning(card.id)
    _protect(bench, card.id, card.candidate_id, kind)
    bench.analysis = [word("glare", at(0)), word("linger", at(3, text=CHANGED))]

    bench.rebuild().execute(SOURCE, mode)

    kept = bench.occurrences.get(card.id)
    assert kept is not None
    assert (kept.source_phrase.text, kept.revision) == (LINES[3], 0)
    assert kept.meaning is not None


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("kind", PROTECTED)
def test_a_protected_card_the_analysis_lost_stays_with_its_word(
    bench: Bench, kind: str, mode: RebuildMode,
) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    card = bench.phrase_on("linger", 3)
    _protect(bench, card.id, card.candidate_id, kind)
    bench.analysis = [word("glare", at(0))]

    summary = bench.rebuild().execute(SOURCE, mode)

    assert bench.occurrences.get(card.id) is not None
    assert "linger" in {w.lemma for w in bench.occurrences.word_rows(SOURCE)}
    assert summary.counts.words_removed == 0


# ── a second rebuild, preview and counts ──────────────────────────────


def test_a_second_rebuild_changes_nothing(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 50.0), at(1, 40.0)), word("linger", at(3)))
    bench.give_meaning(bench.phrase_on("glare", 1).id)
    bench.analysis = [
        word("glare", at(0, 50.0), at(2, 10.0), at(5, 30.0, text="I glared.")),
        word("linger", at(4)),
    ]
    bench.rebuild().execute(SOURCE, RECUT)
    before = [(p.id, p.line, p.shown_by, p.revision, p.source_phrase) for p in bench.phrases()]

    again = bench.rebuild().execute(SOURCE, RECUT)

    assert again.counts.nothing_to_update
    assert bench.rebuild().preview(SOURCE, UPDATE).counts.nothing_to_update
    assert bench.rebuild().preview(SOURCE, RECUT).counts.nothing_to_update
    after = [(p.id, p.line, p.shown_by, p.revision, p.source_phrase) for p in bench.phrases()]
    assert after == before


def test_the_summary_counts_what_changed(bench: Bench) -> None:
    bench.processed(word("glare", at(0)), word("linger", at(3)))
    bench.analysis = [word("glare", at(0)), word("ponder", at(1)), word("muse", at(2))]

    summary = bench.rebuild().execute(SOURCE, UPDATE)

    counts = summary.counts
    assert (counts.words_added, counts.words_removed) == (2, 1)
    assert not counts.nothing_to_update
    assert summary.mode is UPDATE


def test_the_preview_changes_nothing_and_counts_the_mode_asked_for(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 50.0)))
    generated = bench.phrase_on("glare", 0)
    bench.give_meaning(generated.id)
    bench.analysis = [word("glare", at(0, 50.0, text=CHANGED), at(2, 10.0))]
    before = [(p.id, p.shown_by, p.source_phrase) for p in bench.phrases()]

    update = bench.rebuild().preview(SOURCE, UPDATE)
    recut = bench.rebuild().preview(SOURCE, RECUT)

    assert (update.mode, update.counts.cards_moved, update.counts.cards_recut) == (UPDATE, 1, 0)
    assert (recut.mode, recut.counts.cards_moved, recut.counts.cards_recut) == (RECUT, 1, 1)
    assert [(p.id, p.shown_by, p.source_phrase) for p in bench.phrases()] == before
    assert bench.lock.held(SOURCE) is None


# ── the lock and the sources that cannot be rebuilt ───────────────────


def test_a_busy_source_is_refused(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    bench.lock.acquire(SOURCE, SourceOperationKind.PROCESS)
    bench.session.commit()
    bench.analyze_text.execute.reset_mock()

    with pytest.raises(SourceOperationBusyError):
        bench.rebuild().execute(SOURCE, UPDATE)
    with pytest.raises(SourceOperationBusyError):
        bench.rebuild().preview(SOURCE, UPDATE)

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

    bench.rebuild().execute(SOURCE, UPDATE)
    bench.rebuild().preview(SOURCE, UPDATE)

    assert held == [SourceOperationKind.UPDATE, SourceOperationKind.PREVIEW]
    assert bench.lock.held(SOURCE) is None


def test_a_failed_rebuild_releases_the_lock_and_writes_nothing(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    before = [(p.id, p.shown_by) for p in bench.phrases()]
    bench.analyze_text.execute.side_effect = RuntimeError("parser crashed")

    with pytest.raises(RuntimeError):
        bench.rebuild().execute(SOURCE, RECUT)

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
        bench.rebuild().execute(SOURCE, UPDATE)

    assert bench.phrases() == []


def test_a_source_never_processed_is_not_rebuilt(db_session: Session) -> None:
    """Rebuild is what the source offers once processed; a new one is processed instead."""
    bench = Bench(db_session, status="new")

    with pytest.raises(RebuildNotSupportedError):
        bench.rebuild().execute(SOURCE, UPDATE)
    with pytest.raises(RebuildNotSupportedError):
        bench.rebuild().preview(SOURCE, UPDATE)

    assert bench.lock.held(SOURCE) is None


# ── source status ─────────────────────────────────────────────────────


def test_a_source_in_error_is_processed_again(db_session: Session) -> None:
    bench = Bench(db_session, status="error")
    bench.analysis = [word("glare", at(0))]

    bench.rebuild().execute(SOURCE, UPDATE)

    assert bench.status() == "done"
    assert bench.shown_lines("glare") == [0]


def test_a_reviewed_source_with_a_new_word_is_partly_reviewed(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    bench.decide_learn("glare", bench.phrase_on("glare", 0).id)
    assert bench.review_status() == "reviewed"
    bench.analysis = [word("glare", at(0)), word("linger", at(3))]

    bench.rebuild().execute(SOURCE, UPDATE)

    assert (bench.status(), bench.review_status()) == ("done", "partially_reviewed")


# ── media timecodes (video sources) ───────────────────────────────────


def test_a_new_phrase_of_a_video_gets_the_time_of_its_line(video: Bench) -> None:
    video.processed(word("glare", at(0)))
    video.analysis = [word("glare", at(0)), word("linger", at(3)), word("ponder", at(4))]

    video.rebuild().execute(SOURCE, UPDATE)

    assert video.times(video.phrase_on("linger", 3).id) == time_of_line(3)
    assert video.times(video.phrase_on("ponder", 4).id) == time_of_line(4)


def test_a_recut_phrase_of_a_video_gets_the_time_of_its_new_lines(video: Bench) -> None:
    video.processed(word("glare", at(0)))
    phrase = video.phrase_on("glare", 0)
    assert video.times(phrase.id) == time_of_line(0)
    two_lines = _spanning(0, 1)
    video.analysis = [word("glare", two_lines)]

    video.rebuild().execute(SOURCE, RECUT)

    assert video.times(phrase.id) == (time_of_line(0)[0], time_of_line(1)[1])


def test_an_update_keeps_a_made_clip_and_the_time_it_was_cut_at(video: Bench) -> None:
    video.processed(word("glare", at(0)))
    phrase = video.phrase_on("glare", 0)
    video.give_clip(phrase.id, 10, 20)
    video.analysis = [word("glare", _spanning(0, 1))]

    video.rebuild().execute(SOURCE, UPDATE)

    assert video.times(phrase.id) == (10, 20)


@pytest.mark.parametrize("mode", MODES)
def test_a_made_clip_keeps_its_time_when_its_phrase_gets_new_facts(
    video: Bench, mode: RebuildMode,
) -> None:
    video.processed(word("glare", at(0)))
    phrase = video.phrase_on("glare", 0)
    video.give_clip(phrase.id, 10, 20)
    same_text = at(0).model_copy(update={"phrase": text_phrase(LINES[0], variant=True)})
    video.analysis = [word("glare", same_text)]

    summary = video.rebuild().execute(SOURCE, mode)

    assert summary.counts.cards_recut == 0
    assert video.times(phrase.id) == (10, 20)
    assert video.media_files.removed == []


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
        fragment_score=50.0,
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


def _queued_job(bench: Bench, phrase_id: int, word_id: int) -> None:
    bench.jobs.enqueue([Job.queued(
        JobType.MEANING, SOURCE, word_id, phrase_id=phrase_id, phrase_revision=0,
    )])
    bench.session.commit()


def _job_revisions(bench: Bench) -> list[int | None]:
    bench.session.expire_all()
    return list(bench.session.scalars(select(JobModel.phrase_revision)))


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

    bench.rebuild().execute(SOURCE, UPDATE)

    earned = _earned(bench)
    assert earned[open_phrase.id] == "ready"
    assert earned[chosen.id] == "extra"


def test_a_preview_that_only_moves_sections_offers_rebuild(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    bench.session.execute(text("UPDATE phrases SET earned_section = 'extra'"))
    bench.session.commit()

    preview = bench.rebuild().preview(SOURCE, UPDATE)

    assert not preview.counts.nothing_to_update
    assert preview.counts.words_added == 0
    assert preview.counts.cards_moved == 0


# ── sources without text of their own: sections only ──────────────────

COLLECTED_TEXT = "He glared at me."


def _collected(bench: Bench, lemma: str, origin: OccurrenceOrigin) -> int:
    seeded = store_card(
        bench.session,
        StoredCandidate(
            source_id=SOURCE, lemma=lemma, pos="VERB", cefr_level="B2",
            zipf_frequency=3.0, occurrences=1, status=WordStatus.NEW,
        ),
        phrase(COLLECTED_TEXT, lemma),
        origin=origin,
    )
    bench.session.commit()
    return seeded.phrase_id


def _everything_but_sections(bench: Bench) -> list[tuple[object, ...]]:
    rows = bench.session.execute(text(
        "SELECT id, candidate_id, source_phrase, polished_phrase, shown_by, choice, revision,"
        " origin, polish_reverted FROM phrases ORDER BY id"
    )).all()
    words = bench.session.execute(text("SELECT * FROM candidates ORDER BY id")).all()
    meanings = bench.session.execute(
        text("SELECT * FROM candidate_meanings ORDER BY phrase_id")
    ).all()
    return [tuple(r) for r in (*rows, *words, *meanings)]


@pytest.mark.parametrize(("role", "origin"), [
    ("topic", OccurrenceOrigin.COLLECTED),
    ("saved_phrases", OccurrenceOrigin.MANUAL),
])
def test_rebuilding_a_source_without_text_restamps_sections_only(
    db_session: Session, role: str, origin: OccurrenceOrigin,
) -> None:
    bench = Bench(db_session, role=role, status="done")
    phrase_id = _collected(bench, "glare", origin)
    bench.give_meaning(phrase_id)
    bench.session.execute(text("UPDATE phrases SET earned_section = 'extra'"))
    bench.session.commit()
    before = _everything_but_sections(bench)

    summary = bench.rebuild().execute(SOURCE, UPDATE)

    assert [p.earned_section for p in bench.phrases()] == ["ready"]
    assert _everything_but_sections(bench) == before
    bench.analyze_text.execute.assert_not_called()
    assert summary.mode is UPDATE
    assert bench.lock.held(SOURCE) is None


@pytest.mark.parametrize("role", ["topic", "saved_phrases"])
def test_a_source_without_text_is_not_recut(db_session: Session, role: str) -> None:
    bench = Bench(db_session, role=role, status="done")

    with pytest.raises(RebuildNotSupportedError):
        bench.rebuild().execute(SOURCE, RECUT)
    with pytest.raises(RebuildNotSupportedError):
        bench.rebuild().preview(SOURCE, RECUT)


def test_an_empty_saved_phrases_source_has_nothing_to_update(db_session: Session) -> None:
    bench = Bench(db_session, role="saved_phrases", status="done")

    preview = bench.rebuild().preview(SOURCE, UPDATE)

    assert preview.counts.nothing_to_update


def test_a_topic_whose_only_change_is_a_section_offers_rebuild(db_session: Session) -> None:
    bench = Bench(db_session, role="topic", status="done")
    _collected(bench, "glare", OccurrenceOrigin.COLLECTED)
    bench.session.execute(text("UPDATE phrases SET earned_section = 'extra'"))
    bench.session.commit()

    assert not bench.rebuild().preview(SOURCE, UPDATE).counts.nothing_to_update


def test_a_content_source_without_document_still_refuses(db_session: Session) -> None:
    bench = Bench(db_session, status="error")
    bench.session.execute(text("DELETE FROM source_documents"))
    bench.session.commit()

    with pytest.raises(SourceHasNoDocumentError):
        bench.rebuild().execute(SOURCE, UPDATE)

    assert bench.status() == "error"
