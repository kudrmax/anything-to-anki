"""JobWorker against a real SQLite queue: order, lifecycle, cancel, timeout, restart."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from backend.domain.entities.job import Job
from backend.domain.exceptions import AIUnavailableError, PermanentAIError
from backend.domain.value_objects.job_selection import JobSelection
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import PHRASE_JOB_TYPES, JobType
from backend.domain.value_objects.meaning_follow_up import MeaningFollowUp
from backend.domain.value_objects.phrase_ref import PhraseRef
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import JobModel
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.session_work import SessionWork
from backend.infrastructure.persistence.sqla_job_queue import SqlaJobQueue
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from backend.infrastructure.queue import job_worker
from backend.infrastructure.queue.job_worker import NO_AI_RESULT_ERROR, JobWorker
from backend.infrastructure.queue.tts_subprocess import process_tts_run
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator, Iterator
    from pathlib import Path

    from backend.application.utils.candidate_filter import CandidateFilter

SOURCE_ID = 1
WRITTEN_TITLE = "written by the job"
SHORT_TICK_S = 0.01
LONG_WAIT_S = 5.0
TICKS_DURING_A_JOB = 2


class _Container:
    """The worker's view of the container: real sessions and queue, fake use cases that
    write through the unit of work of the session they are built on."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory
        self._work = SessionWork(factory, _unit_of_work)
        self.meaning = MagicMock()
        self.polish = MagicMock()
        self.media = MagicMock()
        self.pronunciation = MagicMock()
        self.video = MagicMock()
        self.topic = MagicMock()
        self.follow_up = MagicMock()
        self.cleanup = MagicMock()
        self.tts = MagicMock()
        self.meaning.execute_batch.return_value = []
        self.polish.execute_batch.return_value = []
        self.ticks = threading.Semaphore(0)

    def tick_card_states(self) -> None:
        self.ticks.release()

    def session_work(self) -> SessionWork:
        return self._work

    def job_queue(self) -> SqlaJobQueue:
        return SqlaJobQueue(self._work)

    @contextmanager
    def fixture_session(self) -> Iterator[Session]:
        """The test's own setup and read-back, beside the worker's sessions."""
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def meaning_generation_use_case(self, session: Session) -> MagicMock:
        return self._bound(self.meaning, session)

    def meaning_follow_up_use_case(self, session: Session) -> MagicMock:
        return self._bound(self.follow_up, session)

    def phrase_polish_use_case(self, session: Session) -> MagicMock:
        return self._bound(self.polish, session)

    def media_extraction_use_case(self, session: Session) -> MagicMock:
        return self._bound(self.media, session)

    def download_pronunciation_use_case(self, session: Session) -> MagicMock:
        return self._bound(self.pronunciation, session)

    def download_video_use_case(self, session: Session) -> MagicMock:
        return self._bound(self.video, session)

    def generate_topic_targets_use_case(self, session: Session) -> MagicMock:
        return self._bound(self.topic, session)

    def generate_tts_use_case(self, session: Session) -> MagicMock:
        return self._bound(self.tts, session)

    def cleanup_youtube_video_use_case(self, session: Session) -> MagicMock:
        return self.cleanup

    @staticmethod
    def _bound(use_case: MagicMock, session: Session) -> MagicMock:
        use_case.session = session
        use_case.unit_of_work = _unit_of_work(session)
        return use_case


def _unit_of_work(session: Session) -> SqlaUnitOfWork:
    return SqlaUnitOfWork(session, MagicMock())


SHORT_TIMEOUT_S = 0.2
RUN_PAST_TIMEOUT_S = 0.6


@pytest.fixture()
def factory(tmp_path: Path) -> Generator[sessionmaker[Session], None, None]:
    # A file, not :memory: — sessions must be isolated like in production.
    engine = create_engine(
        f"sqlite:///{tmp_path / 'queue.db'}", connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        session.execute(text(
            "INSERT INTO sources (id, title, status, created_at)"
            " VALUES (:id, 'original', 'done', '2026-01-01 00:00:00')"
        ), {"id": SOURCE_ID})
        for cid in range(1, 10):
            insert_word(session, cid, source_id=SOURCE_ID)
        session.commit()
    yield session_factory
    engine.dispose()


@pytest.fixture()
def container(factory: sessionmaker[Session]) -> _Container:
    return _Container(factory)


def _enqueue(container: _Container, *jobs: tuple[JobType, int | None]) -> list[Job]:
    """A phrase job works on the word's own phrase, `phrase_id_of` the word."""
    with container.fixture_session() as session:
        return SqlaJobRepository(session, SessionChangeRecorder(session)).enqueue([
            Job.queued(
                job_type, SOURCE_ID, candidate_id,
                phrase_id=phrase_id_of(candidate_id) if job_type in PHRASE_JOB_TYPES else None,
                phrase_revision=0 if job_type in PHRASE_JOB_TYPES else None,
            )
            for job_type, candidate_id in jobs
        ])


def _ids(phrases: list[PhraseRef]) -> list[int]:
    return [p.phrase_id for p in phrases]


def _jobs(container: _Container) -> list[tuple[JobType, int | None, JobStatus, str | None]]:
    with container.fixture_session() as session:
        jobs = SqlaJobRepository(
            session, SessionChangeRecorder(session),
        ).get_jobs_by_status(list(JobStatus))
    return [(j.job_type, j.candidate_id, j.status, j.error) for j in jobs]


def _title(container: _Container) -> str:
    with container.fixture_session() as session:
        return str(session.execute(
            text("SELECT title FROM sources WHERE id = :id"), {"id": SOURCE_ID},
        ).scalar_one())


def _write_title(use_case: MagicMock) -> None:
    with use_case.unit_of_work.write():
        _update_title(use_case)


def _update_title(use_case: MagicMock) -> None:
    use_case.session.execute(
        text("UPDATE sources SET title = :t WHERE id = :id"),
        {"t": WRITTEN_TITLE, "id": SOURCE_ID},
    )


def _cancel(container: _Container, selection: JobSelection) -> None:
    with container.fixture_session() as session:
        SqlaJobRepository(session, SessionChangeRecorder(session)).cancel(selection)


async def _drain(worker: JobWorker) -> None:
    while await worker._process_one_job():
        pass


@pytest.mark.integration
class TestOrder:
    async def test_runs_follow_the_queue_and_batch_only_neighbours(
        self, container: _Container,
    ) -> None:
        _enqueue(
            container,
            (JobType.POLISH, 1), (JobType.POLISH, 2), (JobType.MEANING, 3), (JobType.POLISH, 4),
        )
        calls: list[tuple[str, list[int]]] = []
        container.polish.execute_batch.side_effect = (
            lambda phrases, wanted: calls.append(("polish", _ids(phrases))) or []
        )
        container.meaning.execute_batch.side_effect = (
            lambda phrases, wanted: calls.append(("meaning", _ids(phrases))) or []
        )

        await _drain(JobWorker(container))  # type: ignore[arg-type]

        assert calls == [
            ("polish", [phrase_id_of(1), phrase_id_of(2)]), ("meaning", [phrase_id_of(3)]),
            ("polish", [phrase_id_of(4)]),
        ]
        assert _jobs(container) == []

    async def test_an_ai_batch_takes_interleaved_sources_of_a_set(
        self, container: _Container,
    ) -> None:
        other_source = SOURCE_ID + 1
        with container.fixture_session() as session:
            session.execute(text(
                "INSERT INTO sources (id, title, status, created_at)"
                " VALUES (:id, 'other', 'done', '2026-01-01 00:00:00')"
            ), {"id": other_source})
            for cid in (11, 12):
                insert_word(session, cid, source_id=other_source)
            SqlaJobRepository(session, SessionChangeRecorder(session)).enqueue([
                Job.queued(
                    JobType.POLISH, source_id, cid,
                    phrase_id=phrase_id_of(cid), phrase_revision=0,
                )
                for source_id, cid in (
                    (SOURCE_ID, 1), (other_source, 11), (SOURCE_ID, 2), (other_source, 12),
                )
            ])
        calls: list[list[int]] = []
        container.polish.execute_batch.side_effect = (
            lambda phrases, wanted: calls.append(_ids(phrases)) or []
        )

        await _drain(JobWorker(container))  # type: ignore[arg-type]

        assert calls == [[phrase_id_of(c) for c in (1, 11, 2, 12)]]
        assert _jobs(container) == []


@pytest.mark.integration
class TestPhraseGone:
    async def test_a_job_whose_phrase_a_rebuild_deleted_finishes_without_error(
        self, container: _Container, factory: sessionmaker[Session],
    ) -> None:
        _enqueue(container, (JobType.MEANING, 1))

        def rebuild_deletes_the_phrase(phrases: list[PhraseRef], wanted: object) -> list[int]:
            with factory() as other:
                other.execute(text("PRAGMA foreign_keys = ON"))
                other.execute(text("DELETE FROM phrases WHERE id = 1"))
                other.commit()
            return []

        container.meaning.execute_batch.side_effect = rebuild_deletes_the_phrase

        await _drain(JobWorker(container))  # type: ignore[arg-type]

        assert _jobs(container) == []

    async def test_the_worker_hands_the_jobs_phrases_to_the_use_case(
        self, container: _Container,
    ) -> None:
        with container.fixture_session() as session:
            SqlaJobRepository(session, SessionChangeRecorder(session)).enqueue([
                Job.queued(
                    JobType.TTS, SOURCE_ID, 1, phrase_id=phrase_id_of(1), phrase_revision=4,
                ),
            ])
        container.tts.execute_one.side_effect = lambda ref: None

        with patch.object(JobWorker, "_run_tts_subprocess", _tts_in_process(container)):
            await _drain(JobWorker(container))  # type: ignore[arg-type]

        container.tts.execute_one.assert_called_once_with(PhraseRef(phrase_id_of(1), 4))


def _tts_in_process(container: _Container) -> Callable[[JobWorker, Job], Awaitable[None]]:
    async def run(_worker: JobWorker, job: Job) -> None:
        assert job.id is not None
        process_tts_run(container, job.id)  # type: ignore[arg-type]
    return run


@pytest.mark.integration
class TestLifecycle:
    async def test_success_writes_result_and_clears_old_failure(
        self, container: _Container,
    ) -> None:
        _enqueue(container, (JobType.MEDIA, 1))
        with container.fixture_session() as session:
            # e.g. a failure left by an earlier attempt made outside the queue
            stale = Job.queued(
                JobType.MEDIA, SOURCE_ID, 1, phrase_id=phrase_id_of(1), phrase_revision=0,
            )
            session.add(JobModel.from_entity(stale))
            session.flush()
            session.execute(text(
                "UPDATE jobs SET status = 'failed', error = 'old' WHERE id = "
                "(SELECT MAX(id) FROM jobs)"
            ))
        container.media.execute_one.side_effect = lambda cid: _write_title(container.media)

        await _drain(JobWorker(container))  # type: ignore[arg-type]

        assert _title(container) == WRITTEN_TITLE
        assert _jobs(container) == []
        container.cleanup.execute.assert_called_once_with(SOURCE_ID)

    async def test_cards_ai_left_unanswered_fail_and_the_rest_complete(
        self, container: _Container,
    ) -> None:
        _enqueue(container, (JobType.MEANING, 1), (JobType.MEANING, 2))
        container.meaning.execute_batch.return_value = [phrase_id_of(2)]

        await _drain(JobWorker(container))  # type: ignore[arg-type]

        assert _jobs(container) == [(JobType.MEANING, 2, JobStatus.FAILED, NO_AI_RESULT_ERROR)]

    @pytest.mark.parametrize(("error", "message"), [
        (PermanentAIError("model unavailable"), "model unavailable"),
        (RuntimeError("boom"), "RuntimeError: boom"),
    ])
    async def test_error_fails_the_whole_run_and_rolls_back_the_open_write(
        self, container: _Container, error: Exception, message: str,
    ) -> None:
        _enqueue(container, (JobType.POLISH, 1), (JobType.POLISH, 2))

        def write_then_raise(phrases: list[PhraseRef], wanted: CandidateFilter) -> list[int]:
            with container.polish.unit_of_work.write():
                _update_title(container.polish)
                raise error

        container.polish.execute_batch.side_effect = write_then_raise

        await _drain(JobWorker(container))  # type: ignore[arg-type]

        assert _title(container) == "original"
        assert _jobs(container) == [
            (JobType.POLISH, 1, JobStatus.FAILED, message),
            (JobType.POLISH, 2, JobStatus.FAILED, message),
        ]

    async def test_write_committed_before_a_failure_survives_it(
        self, container: _Container,
    ) -> None:
        _enqueue(container, (JobType.POLISH, 1))

        def write_then_raise(phrases: list[PhraseRef], wanted: CandidateFilter) -> list[int]:
            _write_title(container.polish)
            raise RuntimeError("boom")

        container.polish.execute_batch.side_effect = write_then_raise

        await _drain(JobWorker(container))  # type: ignore[arg-type]

        assert _title(container) == WRITTEN_TITLE
        assert _jobs(container) == [
            (JobType.POLISH, 1, JobStatus.FAILED, "RuntimeError: boom"),
        ]

    async def test_timeout_fails_jobs_and_drops_late_result(
        self, container: _Container,
    ) -> None:
        _enqueue(container, (JobType.PRONUNCIATION, 1))
        release = threading.Event()
        finished = threading.Event()

        def slow(cid: int) -> None:
            release.wait(5)
            _write_title(container.pronunciation)

        container.pronunciation.execute_one.side_effect = slow
        original_execute = JobWorker._execute

        def tracked(worker: JobWorker, run: object) -> set[int]:
            try:
                return original_execute(worker, run)  # type: ignore[arg-type]
            finally:
                finished.set()

        with (
            patch.object(job_worker, "JOB_TIMEOUT", 0.2),
            patch.object(JobWorker, "_execute", tracked),
        ):
            await _drain(JobWorker(container))  # type: ignore[arg-type]
            release.set()
            await asyncio.to_thread(finished.wait, 5)

        assert _jobs(container) == [
            (JobType.PRONUNCIATION, 1, JobStatus.FAILED, job_worker.TIMEOUT_ERROR),
        ]
        assert _title(container) == "original"


@pytest.mark.integration
class TestLevelChangeWait:
    async def test_wait_at_gate_does_not_count(self, container: _Container) -> None:
        """A run whose writes wait out a level change past the timeout is not failed: the
        wait is not its own time."""
        _enqueue(container, (JobType.PRONUNCIATION, 1))
        started = time.monotonic()

        def waiting_all_along() -> float:
            return time.monotonic() - started

        def slow(cid: int) -> None:
            time.sleep(RUN_PAST_TIMEOUT_S)
            _write_title(container.pronunciation)

        container.pronunciation.execute_one.side_effect = slow

        with patch.object(job_worker, "JOB_TIMEOUT", SHORT_TIMEOUT_S):
            await _drain(JobWorker(container, waited_seconds=waiting_all_along))  # type: ignore[arg-type]

        assert _jobs(container) == []
        assert _title(container) == WRITTEN_TITLE


@pytest.mark.integration
class TestCancel:
    async def test_cancelled_run_drops_its_result(self, container: _Container) -> None:
        _enqueue(container, (JobType.TOPIC_TARGETS, None))

        def cancel_midway(source_id: int) -> None:
            _cancel(container, JobSelection(job_type=JobType.TOPIC_TARGETS))
            _write_title(container.topic)

        container.topic.execute.side_effect = cancel_midway

        await _drain(JobWorker(container))  # type: ignore[arg-type]

        assert _title(container) == "original"
        assert _jobs(container) == []

    async def test_cancel_after_the_write_keeps_it_and_says_so(
        self, container: _Container, caplog: pytest.LogCaptureFixture,
    ) -> None:
        _enqueue(container, (JobType.TOPIC_TARGETS, None))

        def write_then_get_cancelled(source_id: int) -> None:
            _write_title(container.topic)
            _cancel(container, JobSelection(job_type=JobType.TOPIC_TARGETS))

        container.topic.execute.side_effect = write_then_get_cancelled

        with caplog.at_level(logging.INFO, logger=job_worker.__name__):
            await _drain(JobWorker(container))  # type: ignore[arg-type]

        assert _title(container) == WRITTEN_TITLE
        assert _jobs(container) == []
        assert "what was written before that stays" in caplog.text
        assert "result dropped" not in caplog.text

    async def test_batch_writes_only_for_jobs_still_wanted(
        self, container: _Container,
    ) -> None:
        jobs = _enqueue(container, (JobType.MEANING, 1), (JobType.MEANING, 2))
        seen: list[set[int]] = []

        def cancel_one(
            phrases: list[PhraseRef], wanted: Callable[[list[int]], set[int]],
        ) -> list[int]:
            _cancel(container, JobSelection(job_id=jobs[1].id))
            seen.append(wanted(_ids(phrases)))
            return []

        container.meaning.execute_batch.side_effect = cancel_one

        await _drain(JobWorker(container))  # type: ignore[arg-type]

        assert seen == [{phrase_id_of(1)}]
        assert _jobs(container) == []


NOT_LOGGED_IN = "Not logged in · Please run /login"


@pytest.mark.integration
class TestMeaningFollowUp:
    async def test_the_worker_asks_the_question_the_job_was_queued_with(
        self, container: _Container,
    ) -> None:
        follow_up = MeaningFollowUp("free_question", "Is it formal?")
        with container.fixture_session() as session:
            SqlaJobRepository(session, SessionChangeRecorder(session)).enqueue([Job.queued(
                JobType.MEANING_FOLLOW_UP, SOURCE_ID, 1,
                phrase_id=phrase_id_of(1), phrase_revision=0, follow_up=follow_up,
            )])

        await _drain(JobWorker(container))  # type: ignore[arg-type]

        container.follow_up.execute_follow_up.assert_called_once_with(phrase_id_of(1), follow_up)
        assert _jobs(container) == []


@pytest.mark.integration
class TestAIOutage:
    @pytest.fixture(autouse=True)
    def _no_retry_delay(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(job_worker, "AI_RETRY_DELAY", 0)

    async def test_the_run_goes_back_in_line_and_the_queue_waits(
        self, container: _Container,
    ) -> None:
        _enqueue(container, (JobType.POLISH, 1), (JobType.POLISH, 2), (JobType.MEDIA, 3))

        def write_then_raise(phrases: list[PhraseRef], wanted: CandidateFilter) -> list[int]:
            with container.polish.unit_of_work.write():
                _update_title(container.polish)
                raise AIUnavailableError(NOT_LOGGED_IN)

        container.polish.execute_batch.side_effect = write_then_raise

        await JobWorker(container)._process_one_job()  # type: ignore[arg-type]

        assert _title(container) == "original"
        assert _jobs(container) == [
            (JobType.POLISH, 1, JobStatus.QUEUED, NOT_LOGGED_IN),
            (JobType.POLISH, 2, JobStatus.QUEUED, NOT_LOGGED_IN),
            (JobType.MEDIA, 3, JobStatus.QUEUED, None),
        ]
        container.media.execute_one.assert_not_called()

    async def test_the_queue_goes_on_once_the_ai_answers(self, container: _Container) -> None:
        _enqueue(container, (JobType.POLISH, 1), (JobType.MEDIA, 2))
        container.polish.execute_batch.side_effect = [AIUnavailableError(NOT_LOGGED_IN), []]
        worker = JobWorker(container)  # type: ignore[arg-type]

        await worker._process_one_job()
        await _drain(worker)

        assert _jobs(container) == []
        assert container.polish.execute_batch.call_count == 2
        container.media.execute_one.assert_called_once()

    async def test_shutdown_ends_the_wait_for_the_ai(
        self, container: _Container, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(job_worker, "AI_RETRY_DELAY", 3600)
        _enqueue(container, (JobType.TOPIC_TARGETS, None))
        container.topic.execute.side_effect = AIUnavailableError(NOT_LOGGED_IN)
        worker = JobWorker(container)  # type: ignore[arg-type]

        waiting = asyncio.create_task(worker._process_one_job())
        while not container.topic.execute.called:
            await asyncio.sleep(0.01)
        worker._request_shutdown()

        assert await asyncio.wait_for(waiting, timeout=5)


@pytest.mark.integration
class TestRestartAndTTS:
    def test_startup_puts_interrupted_jobs_back_in_line(self, container: _Container) -> None:
        _enqueue(container, (JobType.MEDIA, 1))
        with container.fixture_session() as session:
            SqlaJobRepository(session, SessionChangeRecorder(session)).claim_next_run({})

        JobWorker(container)._reconcile_on_startup()  # type: ignore[arg-type]

        assert _jobs(container) == [(JobType.MEDIA, 1, JobStatus.QUEUED, None)]

    async def test_tts_subprocess_gets_the_claimed_job(self, container: _Container) -> None:
        jobs = _enqueue(container, (JobType.TTS, 1))
        process = MagicMock()
        process.returncode = None

        async def wait() -> int:
            return 0

        process.wait = wait
        spawn = MagicMock()

        async def spawn_process(*args: str) -> MagicMock:
            spawn(*args)
            return process

        with patch.object(job_worker.asyncio, "create_subprocess_exec", spawn_process):
            assert await JobWorker(container)._process_one_job()  # type: ignore[arg-type]

        assert spawn.call_args.args[-1] == str(jobs[0].id)

    async def test_tts_crash_fails_its_running_job(self, container: _Container) -> None:
        _enqueue(container, (JobType.TTS, 1), (JobType.TTS, 2))
        process = MagicMock()
        process.returncode = None

        async def crash() -> int:
            return -9

        process.wait = crash

        async def spawn_process(*args: str) -> MagicMock:
            return process

        with patch.object(job_worker.asyncio, "create_subprocess_exec", spawn_process):
            await JobWorker(container)._process_one_job()  # type: ignore[arg-type]

        assert _jobs(container) == [
            (JobType.TTS, 1, JobStatus.FAILED, "TTS worker exited with code -9"),
            (JobType.TTS, 2, JobStatus.QUEUED, None),
        ]


def _claim_head(container: _Container) -> Job:
    with container.fixture_session() as session:
        return SqlaJobRepository(session, SessionChangeRecorder(session)).claim_next_run({})[0]


@pytest.mark.integration
class TestTTSSubprocess:
    def test_processes_tts_while_it_heads_the_queue(self, container: _Container) -> None:
        _enqueue(
            container,
            (JobType.TTS, 1), (JobType.TTS, 2), (JobType.POLISH, 3), (JobType.TTS, 4),
        )
        first = _claim_head(container)
        assert first.id is not None

        processed = process_tts_run(container, first.id)  # type: ignore[arg-type]

        assert processed == 2
        assert [c.args[0] for c in container.tts.execute_one.call_args_list] == [
            PhraseRef(phrase_id_of(1), 0), PhraseRef(phrase_id_of(2), 0),
        ]
        assert _jobs(container) == [
            (JobType.POLISH, 3, JobStatus.QUEUED, None),
            (JobType.TTS, 4, JobStatus.QUEUED, None),
        ]

    def test_stops_when_its_worker_is_gone(self, container: _Container) -> None:
        _enqueue(container, (JobType.TTS, 1), (JobType.TTS, 2))
        first = _claim_head(container)
        assert first.id is not None

        processed = process_tts_run(
            container, first.id, worker_alive=lambda: False,  # type: ignore[arg-type]
        )

        assert processed == 1
        assert _jobs(container) == [(JobType.TTS, 2, JobStatus.QUEUED, None)]

    def test_failure_fails_only_that_job(self, container: _Container) -> None:
        _enqueue(container, (JobType.TTS, 1), (JobType.TTS, 2))
        first = _claim_head(container)
        assert first.id is not None
        container.tts.execute_one.side_effect = [RuntimeError("no voice"), None]

        process_tts_run(container, first.id)  # type: ignore[arg-type]

        assert _jobs(container) == [
            (JobType.TTS, 1, JobStatus.FAILED, "RuntimeError: no voice"),
        ]

    def test_job_cancelled_before_start_is_skipped(self, container: _Container) -> None:
        _enqueue(container, (JobType.TTS, 1))
        first = _claim_head(container)
        assert first.id is not None
        _cancel(container, JobSelection(job_id=first.id))

        assert process_tts_run(container, first.id) == 0  # type: ignore[arg-type]
        container.tts.execute_one.assert_not_called()

    def test_job_cancelled_midway_drops_its_result(self, container: _Container) -> None:
        _enqueue(container, (JobType.TTS, 1))
        first = _claim_head(container)
        assert first.id is not None

        def cancel_then_write(cid: int) -> None:
            _cancel(container, JobSelection(job_id=first.id))
            _write_title(container.tts)

        container.tts.execute_one.side_effect = cancel_then_write

        process_tts_run(container, first.id)  # type: ignore[arg-type]

        assert _title(container) == "original"
        assert _jobs(container) == []


@pytest.mark.integration
class TestCardStateTick:
    async def test_time_ticks_while_a_job_runs_for_long(self, container: _Container) -> None:
        """The tick is its own task: a run that takes minutes does not hold it back."""
        _enqueue(container, (JobType.MEANING, 1))
        ticked_during_the_job = threading.Event()

        def long_run(phrases: list[PhraseRef], wanted: CandidateFilter) -> list[int]:
            del phrases, wanted
            for _ in range(TICKS_DURING_A_JOB):
                assert container.ticks.acquire(timeout=LONG_WAIT_S)
            ticked_during_the_job.set()
            return []

        container.meaning.execute_batch.side_effect = long_run
        worker = JobWorker(container)  # type: ignore[arg-type]
        with patch.object(job_worker, "CARD_STATE_TICK_INTERVAL", SHORT_TICK_S):
            running = asyncio.create_task(worker.run())
            while not ticked_during_the_job.is_set():
                await asyncio.sleep(SHORT_TICK_S)
            worker._request_shutdown()
            await asyncio.wait_for(running, timeout=LONG_WAIT_S)

        assert _jobs(container) == []

    async def test_a_failed_tick_is_logged_and_the_next_one_runs(
        self, container: _Container, caplog: pytest.LogCaptureFixture,
    ) -> None:
        calls: list[int] = []

        def failing_once() -> None:
            calls.append(len(calls))
            if len(calls) == 1:
                raise RuntimeError("tick broke")

        container.tick_card_states = failing_once  # type: ignore[method-assign]
        worker = JobWorker(container)  # type: ignore[arg-type]
        with patch.object(job_worker, "CARD_STATE_TICK_INTERVAL", SHORT_TICK_S):
            running = asyncio.create_task(worker.run())
            while len(calls) < TICKS_DURING_A_JOB:
                await asyncio.sleep(SHORT_TICK_S)
            worker._request_shutdown()
            await asyncio.wait_for(running, timeout=LONG_WAIT_S)

        assert "Card state time tick failed" in caplog.text

    async def test_failed_ticks_in_a_row_become_errors_and_a_success_resets_them(
        self, container: _Container, caplog: pytest.LogCaptureFixture,
    ) -> None:
        outcomes = [False, False, False, False, True, False]
        calls: list[int] = []

        def tick() -> None:
            calls.append(len(calls))
            if len(calls) <= len(outcomes) and not outcomes[len(calls) - 1]:
                raise RuntimeError("tick broke")

        container.tick_card_states = tick  # type: ignore[method-assign]
        worker = JobWorker(container)  # type: ignore[arg-type]
        with (
            caplog.at_level(logging.WARNING, logger=job_worker.__name__),
            patch.object(job_worker, "CARD_STATE_TICK_INTERVAL", SHORT_TICK_S),
        ):
            running = asyncio.create_task(worker.run())
            while len(calls) < len(outcomes):
                await asyncio.sleep(SHORT_TICK_S)
            worker._request_shutdown()
            await asyncio.wait_for(running, timeout=LONG_WAIT_S)

        ticks = [
            (record.levelno, record.getMessage()) for record in caplog.records
            if record.getMessage().startswith("Card state time tick failed")
        ]
        assert ticks[:5] == [
            (logging.WARNING, "Card state time tick failed (1 in a row)"),
            (logging.WARNING, "Card state time tick failed (2 in a row)"),
            (logging.ERROR, "Card state time tick failed (3 in a row)"),
            (logging.ERROR, "Card state time tick failed (4 in a row)"),
            (logging.WARNING, "Card state time tick failed (1 in a row)"),
        ]
