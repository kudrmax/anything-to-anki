from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.job import Job
from backend.domain.value_objects.job_selection import UNKNOWN_JOB_ERROR, JobSelection
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.persistence.models import JobModel
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _insert_source(session: Session, source_id: int) -> None:
    session.execute(text(
        "INSERT INTO sources (id, raw_text, status, input_method, content_type, created_at) "
        "VALUES (:id, 'text', 'new', 'text_pasted', 'text', '2026-01-01 00:00:00')"
    ), {"id": source_id})
    session.flush()


def _insert_candidate(session: Session, candidate_id: int, source_id: int) -> None:
    session.execute(text(
        "INSERT INTO candidates (id, source_id, lemma, pos, "
        "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
        "occurrences, status, is_phrasal_verb, has_custom_context_fragment) "
        "VALUES (:id, :sid, 'word', 'NOUN', 3.0, 0, 'ctx', 'clean', 1, 'pending', 0, 0)"
    ), {"id": candidate_id, "sid": source_id})
    session.flush()


def _insert(session: Session, jobs: list[Job]) -> list[Job]:
    """Put jobs in any state straight into the table, bypassing enqueue rules."""
    models = [JobModel.from_entity(j) for j in jobs]
    session.add_all(models)
    session.flush()
    return [m.to_entity() for m in models]


def _make_job(
    job_type: JobType = JobType.MEANING,
    candidate_id: int | None = 1,
    source_id: int = 1,
    status: JobStatus = JobStatus.QUEUED,
    error: str | None = None,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
) -> Job:
    return Job(
        id=None,
        job_type=job_type,
        candidate_id=candidate_id,
        source_id=source_id,
        status=status,
        error=error,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=UTC),
        started_at=started_at,
    )


@pytest.mark.integration
class TestSqlaJobRepository:

    def _setup_source_and_candidate(
        self, session: Session,
        source_id: int = 1,
        candidate_id: int = 1,
    ) -> None:
        _insert_source(session, source_id)
        _insert_candidate(session, candidate_id, source_id)

    # --- claim_next_run ---

    def test_claim_next_run_returns_oldest_queued(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        t1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)
        _insert(db_session, [
            _make_job(candidate_id=1, created_at=t2),
            _make_job(candidate_id=2, created_at=t1),
        ])

        run = repo.claim_next_run({})
        assert [j.candidate_id for j in run] == [2]
        assert run[0].status == JobStatus.RUNNING
        assert run[0].started_at is not None

    def test_claim_next_run_returns_empty_when_queue_empty(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        assert repo.claim_next_run({}) == []

    def test_claim_next_run_skips_running_and_failed(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, status=JobStatus.RUNNING,
                      started_at=datetime(2026, 1, 1, tzinfo=UTC)),
            _make_job(candidate_id=2, status=JobStatus.FAILED, error="err"),
        ])

        assert repo.claim_next_run({}) == []

    def test_claim_next_run_groups_consecutive_jobs_of_same_type_and_source(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        for cid in (2, 3, 4):
            _insert_candidate(db_session, cid, 1)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, job_type=JobType.MEANING),
            _make_job(candidate_id=2, job_type=JobType.MEANING),
            _make_job(candidate_id=3, job_type=JobType.MEANING),
            _make_job(candidate_id=4, job_type=JobType.MEANING),
        ])

        run = repo.claim_next_run({JobType.MEANING: 3})
        assert [j.candidate_id for j in run] == [1, 2, 3]
        assert all(j.status == JobStatus.RUNNING for j in run)

    def test_claim_next_run_never_overtakes_older_job_of_other_type(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        for cid in (2, 3):
            _insert_candidate(db_session, cid, 1)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [_make_job(candidate_id=1, job_type=JobType.POLISH)])
        _insert(db_session, [_make_job(candidate_id=2, job_type=JobType.MEANING)])
        _insert(db_session, [_make_job(candidate_id=3, job_type=JobType.POLISH)])

        first = repo.claim_next_run({JobType.POLISH: 10})
        second = repo.claim_next_run({JobType.POLISH: 10})
        third = repo.claim_next_run({JobType.POLISH: 10})
        assert [j.candidate_id for j in first] == [1]
        assert [j.candidate_id for j in second] == [2]
        assert [j.candidate_id for j in third] == [3]

    def test_claim_next_run_does_not_mix_sources(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 2, 2)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, source_id=1),
            _make_job(candidate_id=2, source_id=2),
        ])

        run = repo.claim_next_run({JobType.MEANING: 10})
        assert [j.candidate_id for j in run] == [1]

    def test_claim_next_run_respects_accepted_types(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, job_type=JobType.POLISH),
            _make_job(candidate_id=2, job_type=JobType.TTS),
        ])

        assert repo.claim_next_run({}, accepted_types=frozenset({JobType.TTS})) == []
        assert [
            j.candidate_id for j in repo.claim_next_run({})
        ] == [1]
        assert [
            j.candidate_id
            for j in repo.claim_next_run({}, accepted_types=frozenset({JobType.TTS}))
        ] == [2]

    # --- enqueue ---

    def test_enqueue_assigns_ids_and_queues(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        queued = repo.enqueue([_make_job(candidate_id=1), _make_job(candidate_id=2)])

        assert len(queued) == 2
        assert all(j.id is not None and j.status == JobStatus.QUEUED for j in queued)

    @pytest.mark.parametrize("status", [JobStatus.QUEUED, JobStatus.RUNNING])
    def test_enqueue_skips_key_that_is_already_active(
        self, db_session: Session, status: JobStatus,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)
        _insert(db_session, [_make_job(candidate_id=1, status=status)])

        assert repo.enqueue([_make_job(candidate_id=1)]) == []
        assert len(repo.get_jobs_by_status([JobStatus.QUEUED, JobStatus.RUNNING])) == 1

    def test_enqueue_skips_duplicates_within_one_call(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        assert len(repo.enqueue([_make_job(candidate_id=1), _make_job(candidate_id=1)])) == 1

    def test_enqueue_keys_source_level_jobs_by_source(self, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        repo = SqlaJobRepository(db_session)

        def download(source_id: int) -> Job:
            return _make_job(
                job_type=JobType.VIDEO_DOWNLOAD, candidate_id=None, source_id=source_id,
            )

        assert len(repo.enqueue([download(1)])) == 1
        assert repo.enqueue([download(1)]) == []
        assert len(repo.enqueue([download(2)])) == 1

    def test_enqueue_supersedes_failed_job_of_same_key(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)
        _insert(db_session, [
            _make_job(candidate_id=1, status=JobStatus.FAILED, error="boom"),
            _make_job(candidate_id=2, status=JobStatus.FAILED, error="boom"),
        ])

        repo.enqueue([_make_job(candidate_id=1)])

        failed = repo.get_jobs_by_status([JobStatus.FAILED])
        assert [j.candidate_id for j in failed] == [2]

    # --- running_ids / complete / fail ---

    def test_running_ids_drops_cancelled_and_failed(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)
        running, failed = _insert(db_session, [
            _make_job(candidate_id=1, status=JobStatus.RUNNING),
            _make_job(candidate_id=2, status=JobStatus.FAILED, error="timeout"),
        ])
        assert running.id is not None and failed.id is not None

        assert repo.running_ids([running.id, failed.id, 99999]) == {running.id}

    def test_complete_removes_jobs_and_failed_jobs_of_same_key(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)
        running, _, _ = _insert(db_session, [
            _make_job(candidate_id=1, status=JobStatus.RUNNING),
            _make_job(candidate_id=1, status=JobStatus.FAILED, error="old"),
            _make_job(candidate_id=2, status=JobStatus.FAILED, error="other"),
        ])

        repo.complete([running])

        remaining = repo.get_jobs_by_status(list(JobStatus))
        assert [(j.candidate_id, j.status) for j in remaining] == [(2, JobStatus.FAILED)]

    def test_fail_marks_only_running_jobs(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)
        running, queued = _insert(db_session, [
            _make_job(candidate_id=1, status=JobStatus.RUNNING),
            _make_job(candidate_id=2),
        ])
        assert running.id is not None and queued.id is not None

        repo.fail([running.id, queued.id, 99999], "boom")

        failed = repo.get(running.id)
        assert failed is not None and failed.status == JobStatus.FAILED
        assert failed.error == "boom"
        still_queued = repo.get(queued.id)
        assert still_queued is not None and still_queued.status == JobStatus.QUEUED

    def test_requeue_running_returns_jobs_to_their_place(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)
        _insert(db_session, [
            _make_job(candidate_id=1, status=JobStatus.RUNNING,
                      created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)),
            _make_job(candidate_id=2,
                      created_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)),
        ])

        assert repo.requeue_running() == 1
        assert [j.candidate_id for j in repo.claim_next_run({})] == [1]

    def test_fail_running_affects_only_given_type(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)
        _insert(db_session, [
            _make_job(candidate_id=1, job_type=JobType.TTS, status=JobStatus.RUNNING),
            _make_job(candidate_id=2, job_type=JobType.MEDIA, status=JobStatus.RUNNING),
        ])

        assert repo.fail_running(JobType.TTS, "crashed") == 1
        assert [j.job_type for j in repo.get_jobs_by_status([JobStatus.RUNNING])] == [
            JobType.MEDIA,
        ]

    # --- cancel / dismiss / retry ---

    def _mixed_queue(self, session: Session) -> list[Job]:
        _insert_source(session, 1)
        _insert_source(session, 2)
        for cid, sid in ((1, 1), (2, 1), (3, 2), (4, 1)):
            _insert_candidate(session, cid, sid)
        return _insert(session, [
            _make_job(candidate_id=1, source_id=1, job_type=JobType.MEANING),
            _make_job(candidate_id=2, source_id=1, job_type=JobType.TTS,
                      status=JobStatus.RUNNING),
            _make_job(candidate_id=3, source_id=2, job_type=JobType.MEANING),
            _make_job(candidate_id=4, source_id=1, job_type=JobType.MEANING,
                      status=JobStatus.FAILED, error="boom"),
        ])

    @pytest.mark.parametrize(("selection", "left"), [
        (JobSelection(), set()),
        (JobSelection(job_type=JobType.MEANING), {2}),
        (JobSelection(source_id=1), {3}),
        (JobSelection(job_type=JobType.MEANING, source_id=2), {1, 2}),
    ])
    def test_cancel_removes_selected_active_jobs(
        self, db_session: Session, selection: JobSelection, left: set[int],
    ) -> None:
        self._mixed_queue(db_session)
        repo = SqlaJobRepository(db_session)

        cancelled = repo.cancel(selection)

        active = repo.get_jobs_by_status([JobStatus.QUEUED, JobStatus.RUNNING])
        assert {j.candidate_id for j in active} == left
        assert cancelled == 3 - len(left)
        assert len(repo.get_jobs_by_status([JobStatus.FAILED])) == 1

    def test_cancel_single_running_job(self, db_session: Session) -> None:
        jobs = self._mixed_queue(db_session)
        repo = SqlaJobRepository(db_session)

        assert repo.cancel(JobSelection(job_id=jobs[1].id)) == 1
        assert repo.cancel(JobSelection(job_id=jobs[1].id)) == 0

    def test_dismiss_removes_selected_failed_jobs(self, db_session: Session) -> None:
        self._mixed_queue(db_session)
        repo = SqlaJobRepository(db_session)

        assert repo.dismiss(JobSelection(error="other")) == 0
        assert repo.dismiss(JobSelection(error="boom")) == 1
        assert repo.get_jobs_by_status([JobStatus.FAILED]) == []
        assert len(repo.get_jobs_by_status([JobStatus.QUEUED, JobStatus.RUNNING])) == 3

    def test_dismiss_unknown_error_matches_jobs_without_error(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)
        _insert(db_session, [_make_job(status=JobStatus.FAILED, error=None)])

        assert repo.dismiss(JobSelection(error=UNKNOWN_JOB_ERROR)) == 1

    def test_retry_moves_failed_jobs_to_queue_tail(self, db_session: Session) -> None:
        self._mixed_queue(db_session)
        repo = SqlaJobRepository(db_session)

        assert repo.retry(JobSelection(job_type=JobType.MEANING)) == 1

        queued = repo.get_jobs_by_status([JobStatus.QUEUED])
        assert [j.candidate_id for j in queued] == [1, 3, 4]
        assert queued[-1].error is None

    def test_retry_drops_failed_job_whose_key_is_active(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)
        _insert(db_session, [
            _make_job(candidate_id=1),
            _make_job(candidate_id=1, status=JobStatus.FAILED, error="boom"),
        ])

        assert repo.retry(JobSelection()) == 0
        assert repo.get_jobs_by_status([JobStatus.FAILED]) == []
        assert len(repo.get_jobs_by_status([JobStatus.QUEUED])) == 1

    def test_retry_filters_by_error(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)
        _insert(db_session, [
            _make_job(candidate_id=1, status=JobStatus.FAILED, error="a"),
            _make_job(candidate_id=2, status=JobStatus.FAILED, error="b"),
        ])

        assert repo.retry(JobSelection(error="a")) == 1
        assert [j.error for j in repo.get_jobs_by_status([JobStatus.FAILED])] == ["b"]

    # --- get ---

    def test_get(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        created = _insert(db_session, [_make_job()])
        job_id = created[0].id
        assert job_id is not None

        fetched = repo.get(job_id)
        assert fetched is not None
        assert fetched.candidate_id == 1
        assert repo.get(99999) is None

    # --- has_active_jobs_for_source ---

    def test_has_active_jobs_for_source(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        assert repo.has_active_jobs_for_source(1) is False

        _insert(db_session, [_make_job()])
        assert repo.has_active_jobs_for_source(1) is True

    def test_has_active_jobs_for_source_with_type_filter(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [_make_job(job_type=JobType.MEANING)])

        assert repo.has_active_jobs_for_source(
            1, frozenset({JobType.MEANING})
        ) is True
        assert repo.has_active_jobs_for_source(
            1, frozenset({JobType.MEDIA})
        ) is False

    # --- get_queue_summary ---

    def test_get_queue_summary(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        _insert_candidate(db_session, 3, 1)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, job_type=JobType.MEANING),
            _make_job(candidate_id=2, job_type=JobType.MEANING,
                      status=JobStatus.FAILED, error="err"),
            _make_job(candidate_id=3, job_type=JobType.MEDIA),
        ])

        summary = repo.get_queue_summary(1)
        assert summary["meaning"]["queued"] == 1
        assert summary["meaning"]["failed"] == 1
        assert summary["media"]["queued"] == 1

    # --- get_jobs_for_candidates ---

    def test_get_jobs_for_candidates(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, job_type=JobType.MEANING),
            _make_job(candidate_id=2, job_type=JobType.MEANING,
                      status=JobStatus.FAILED, error="err"),
        ])

        mapping = repo.get_jobs_for_candidates([1, 2])
        assert 1 in mapping
        assert 2 in mapping
        assert mapping[1]["meaning"].status == JobStatus.QUEUED
        assert mapping[2]["meaning"].status == JobStatus.FAILED

    def test_get_jobs_for_candidates_prefers_active_over_failed(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        # Same candidate: one failed, one queued
        _insert(db_session, [
            _make_job(candidate_id=1, status=JobStatus.FAILED, error="old"),
            _make_job(candidate_id=1,
                      created_at=datetime(2026, 1, 2, tzinfo=UTC)),
        ])

        mapping = repo.get_jobs_for_candidates([1])
        assert mapping[1]["meaning"].status == JobStatus.QUEUED

    def test_get_jobs_for_candidates_empty_list(
        self, db_session: Session,
    ) -> None:
        repo = SqlaJobRepository(db_session)
        assert repo.get_jobs_for_candidates([]) == {}

    # --- get_queue_summary global ---

    def test_get_queue_summary_global(self, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 2)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, source_id=1, job_type=JobType.MEANING),
            _make_job(candidate_id=2, source_id=2, job_type=JobType.MEANING),
        ])

        summary = repo.get_queue_summary(source_id=None)
        assert summary["meaning"]["queued"] == 2

    # --- get_jobs_by_status ---

    def test_get_jobs_by_status_returns_matching(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        t1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)
        _insert(db_session, [
            _make_job(candidate_id=1, job_type=JobType.MEANING, created_at=t1),
            _make_job(candidate_id=2, job_type=JobType.MEANING,
                      status=JobStatus.FAILED, error="err", created_at=t2),
        ])

        jobs = repo.get_jobs_by_status([JobStatus.QUEUED, JobStatus.RUNNING])
        assert len(jobs) == 1
        assert jobs[0].status == JobStatus.QUEUED
        assert jobs[0].candidate_id == 1

    def test_get_jobs_by_status_ordered_by_created_at(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        t1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)
        _insert(db_session, [
            _make_job(candidate_id=2, created_at=t2),
            _make_job(candidate_id=1, created_at=t1),
        ])

        jobs = repo.get_jobs_by_status([JobStatus.QUEUED])
        assert jobs[0].candidate_id == 1
        assert jobs[1].candidate_id == 2

    def test_get_jobs_by_status_filters_by_source_id(
        self, db_session: Session,
    ) -> None:
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 2)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, source_id=1),
            _make_job(candidate_id=2, source_id=2),
        ])

        jobs = repo.get_jobs_by_status([JobStatus.QUEUED], source_id=1)
        assert len(jobs) == 1
        assert jobs[0].source_id == 1

    def test_get_jobs_by_status_filters_by_job_type(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, job_type=JobType.MEANING),
            _make_job(candidate_id=2, job_type=JobType.MEDIA),
        ])

        jobs = repo.get_jobs_by_status([JobStatus.QUEUED], job_type=JobType.MEDIA)
        assert len(jobs) == 1
        assert jobs[0].job_type == JobType.MEDIA

    def test_get_jobs_by_status_respects_limit(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        _insert_candidate(db_session, 3, 1)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1),
            _make_job(candidate_id=2),
            _make_job(candidate_id=3),
        ])

        jobs = repo.get_jobs_by_status([JobStatus.QUEUED], limit=2)
        assert len(jobs) == 2

    def test_get_jobs_by_status_empty_when_no_match(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        jobs = repo.get_jobs_by_status([JobStatus.RUNNING])
        assert jobs == []

    # --- get_failed_grouped_by_error ---

    def test_get_failed_grouped_by_error_groups_correctly(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        _insert_candidate(db_session, 3, 1)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, status=JobStatus.FAILED, error="timeout"),
            _make_job(candidate_id=2, status=JobStatus.FAILED, error="timeout"),
            _make_job(candidate_id=3, status=JobStatus.FAILED, error="network"),
        ])

        groups = repo.get_failed_grouped_by_error()
        assert len(groups) == 2
        # Ordered by count desc — "timeout" group has 2
        assert groups[0].error == "timeout"
        assert groups[0].count == 2
        assert groups[1].error == "network"
        assert groups[1].count == 1

    def test_get_failed_grouped_by_error_counts_jobs_per_source(
        self, db_session: Session,
    ) -> None:
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 2)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, source_id=1, status=JobStatus.FAILED,
                      error="err"),
            _make_job(candidate_id=2, source_id=2, status=JobStatus.FAILED,
                      error="err"),
        ])

        groups = repo.get_failed_grouped_by_error()
        assert len(groups) == 1
        assert sorted(groups[0].source_ids) == [1, 2]
        assert groups[0].source_counts == {1: 1, 2: 1}

    def test_get_failed_grouped_by_error_filters_by_source_id(
        self, db_session: Session,
    ) -> None:
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 2)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, source_id=1, status=JobStatus.FAILED,
                      error="err"),
            _make_job(candidate_id=2, source_id=2, status=JobStatus.FAILED,
                      error="err"),
        ])

        groups = repo.get_failed_grouped_by_error(source_id=1)
        assert len(groups) == 1
        assert groups[0].source_ids == [1]

    def test_get_failed_grouped_by_error_filters_by_job_type(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, job_type=JobType.MEANING,
                      status=JobStatus.FAILED, error="err"),
            _make_job(candidate_id=2, job_type=JobType.MEDIA,
                      status=JobStatus.FAILED, error="err"),
        ])

        groups = repo.get_failed_grouped_by_error(job_type=JobType.MEDIA)
        assert len(groups) == 1
        assert groups[0].job_type == JobType.MEDIA

    def test_get_failed_grouped_by_error_empty_when_no_failures(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [_make_job()])  # queued, not failed

        groups = repo.get_failed_grouped_by_error()
        assert groups == []

    def test_get_failed_grouped_by_error_orders_by_count_desc(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        _insert_candidate(db_session, 3, 1)
        _insert_candidate(db_session, 4, 1)
        repo = SqlaJobRepository(db_session)

        _insert(db_session, [
            _make_job(candidate_id=1, status=JobStatus.FAILED, error="rare"),
            _make_job(candidate_id=2, status=JobStatus.FAILED, error="common"),
            _make_job(candidate_id=3, status=JobStatus.FAILED, error="common"),
            _make_job(candidate_id=4, status=JobStatus.FAILED, error="common"),
        ])

        groups = repo.get_failed_grouped_by_error()
        assert groups[0].error == "common"
        assert groups[0].count == 3
        assert groups[1].error == "rare"
        assert groups[1].count == 1
