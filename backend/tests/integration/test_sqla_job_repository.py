from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.domain.entities.job import Job
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from sqlalchemy import text
from sqlalchemy.orm import Session


def _insert_source(session: Session, source_id: int) -> None:
    session.execute(text(
        "INSERT INTO sources (id, raw_text, status, input_method, content_type, created_at) "
        "VALUES (:id, 'text', 'new', 'text_pasted', 'text', '2026-01-01 00:00:00')"
    ), {"id": source_id})
    session.flush()


def _insert_candidate(session: Session, candidate_id: int, source_id: int) -> None:
    session.execute(text(
        "INSERT INTO candidates (id, source_id, lemma, pos, cefr_level, "
        "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
        "occurrences, status, is_phrasal_verb, has_custom_context_fragment) "
        "VALUES (:id, :sid, 'word', 'NOUN', 'B2', 3.0, 0, 'ctx', 'clean', 1, 'pending', 0, 0)"
    ), {"id": candidate_id, "sid": source_id})
    session.flush()


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

    # --- create_bulk ---

    def test_create_bulk_assigns_ids(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        jobs = [
            _make_job(candidate_id=1),
            _make_job(candidate_id=2),
        ]
        created = repo.create_bulk(jobs)

        assert len(created) == 2
        assert created[0].id is not None
        assert created[1].id is not None
        assert created[0].id != created[1].id
        assert created[0].status == JobStatus.QUEUED

    # --- dequeue_next ---

    def test_dequeue_next_returns_oldest_queued(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        t1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)
        repo.create_bulk([
            _make_job(candidate_id=1, created_at=t2),
            _make_job(candidate_id=2, created_at=t1),
        ])

        dequeued = repo.dequeue_next()
        assert dequeued is not None
        assert dequeued.candidate_id == 2  # older one
        assert dequeued.status == JobStatus.RUNNING
        assert dequeued.started_at is not None

    def test_dequeue_next_returns_none_when_empty(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        assert repo.dequeue_next() is None

    def test_dequeue_next_skips_running_and_failed(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        repo.create_bulk([
            _make_job(candidate_id=1, status=JobStatus.RUNNING,
                      started_at=datetime(2026, 1, 1, tzinfo=UTC)),
            _make_job(candidate_id=2, status=JobStatus.FAILED, error="err"),
        ])

        assert repo.dequeue_next() is None

    # --- dequeue_batch ---

    def test_dequeue_batch(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        _insert_candidate(db_session, 3, 1)
        repo = SqlaJobRepository(db_session)

        repo.create_bulk([
            _make_job(candidate_id=1, job_type=JobType.MEANING),
            _make_job(candidate_id=2, job_type=JobType.MEANING),
            _make_job(candidate_id=3, job_type=JobType.MEDIA),  # different type
        ])

        batch = repo.dequeue_batch(JobType.MEANING, source_id=1, limit=10)
        assert len(batch) == 2
        assert all(j.status == JobStatus.RUNNING for j in batch)

    # --- mark_failed ---

    def test_mark_failed(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        created = repo.create_bulk([_make_job()])
        job_id = created[0].id
        assert job_id is not None

        repo.mark_failed(job_id, "something broke")

        # Should not be dequeued
        assert repo.dequeue_next() is None

    # --- mark_failed_bulk ---

    def test_mark_failed_bulk(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        created = repo.create_bulk([
            _make_job(candidate_id=1),
            _make_job(candidate_id=2),
        ])
        ids = [j.id for j in created if j.id is not None]
        repo.mark_failed_bulk(ids, "batch error")

        assert repo.dequeue_next() is None

    # --- delete ---

    def test_delete(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        created = repo.create_bulk([_make_job()])
        job_id = created[0].id
        assert job_id is not None

        repo.delete(job_id)
        assert not repo.job_exists(job_id)

    # --- delete_bulk ---

    def test_delete_bulk(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        created = repo.create_bulk([
            _make_job(candidate_id=1),
            _make_job(candidate_id=2),
        ])
        ids = [j.id for j in created if j.id is not None]
        repo.delete_bulk(ids)

        for jid in ids:
            assert not repo.job_exists(jid)

    # --- delete_by_source_and_type ---

    def test_delete_by_source_and_type(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        _insert_candidate(db_session, 3, 1)
        repo = SqlaJobRepository(db_session)

        repo.create_bulk([
            _make_job(candidate_id=1, job_type=JobType.MEANING),
            _make_job(candidate_id=2, job_type=JobType.MEANING,
                      status=JobStatus.RUNNING,
                      started_at=datetime(2026, 1, 1, tzinfo=UTC)),
            _make_job(candidate_id=3, job_type=JobType.MEANING,
                      status=JobStatus.FAILED, error="err"),
        ])

        count = repo.delete_by_source_and_type(1, JobType.MEANING)
        # Deletes queued + running, not failed
        assert count == 2

    # --- delete_failed_by_source_and_type ---

    def test_delete_failed_by_source_and_type(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        repo.create_bulk([
            _make_job(candidate_id=1, status=JobStatus.FAILED, error="err1"),
            _make_job(candidate_id=2),  # queued — should not be returned
        ])

        deleted = repo.delete_failed_by_source_and_type(1, JobType.MEANING)
        assert len(deleted) == 1
        assert deleted[0].candidate_id == 1
        assert deleted[0].error == "err1"

        # The failed job is gone
        assert not repo.job_exists(deleted[0].id)  # type: ignore[arg-type]
        # The queued job is still there
        assert repo.dequeue_next() is not None

    # --- fail_all_running ---

    def test_fail_all_running(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        _insert_candidate(db_session, 2, 1)
        repo = SqlaJobRepository(db_session)

        repo.create_bulk([
            _make_job(candidate_id=1, status=JobStatus.RUNNING,
                      started_at=datetime(2026, 1, 1, tzinfo=UTC)),
            _make_job(candidate_id=2),  # queued — not affected
        ])

        count = repo.fail_all_running("worker restart")
        assert count == 1

        # The queued job is still dequeue-able
        dequeued = repo.dequeue_next()
        assert dequeued is not None
        assert dequeued.candidate_id == 2

    # --- job_exists ---

    def test_job_exists(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        created = repo.create_bulk([_make_job()])
        job_id = created[0].id
        assert job_id is not None

        assert repo.job_exists(job_id) is True
        assert repo.job_exists(99999) is False

    # --- has_active_jobs_for_source ---

    def test_has_active_jobs_for_source(self, db_session: Session) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        assert repo.has_active_jobs_for_source(1) is False

        repo.create_bulk([_make_job()])
        assert repo.has_active_jobs_for_source(1) is True

    def test_has_active_jobs_for_source_with_type_filter(
        self, db_session: Session,
    ) -> None:
        self._setup_source_and_candidate(db_session)
        repo = SqlaJobRepository(db_session)

        repo.create_bulk([_make_job(job_type=JobType.MEANING)])

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

        repo.create_bulk([
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

        repo.create_bulk([
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
        repo.create_bulk([
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

    # --- get_source_ids_with_active_jobs ---

    def test_get_source_ids_with_active_jobs(self, db_session: Session) -> None:
        _insert_source(db_session, 1)
        _insert_source(db_session, 2)
        _insert_candidate(db_session, 1, 1)
        _insert_candidate(db_session, 2, 2)
        repo = SqlaJobRepository(db_session)

        repo.create_bulk([
            _make_job(candidate_id=1, source_id=1, job_type=JobType.MEANING),
            _make_job(candidate_id=2, source_id=2, job_type=JobType.MEANING,
                      status=JobStatus.FAILED, error="err"),
        ])

        ids = repo.get_source_ids_with_active_jobs(JobType.MEANING)
        assert ids == [1]
