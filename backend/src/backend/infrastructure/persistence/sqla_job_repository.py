from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from itertools import takewhile
from typing import TYPE_CHECKING

from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.orm import aliased

from backend.domain.ports.job_repository import DEFAULT_RUN_LIMIT, JobRepository
from backend.domain.value_objects.card_change import CardContentChanged, WordContentChanged
from backend.domain.value_objects.failed_job_group import FailedJobGroup
from backend.domain.value_objects.job_selection import UNKNOWN_JOB_ERROR
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.persistence.models import (
    JobModel,
    PhraseModel,
    SourceModel,
    StoredCandidateModel,
)
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Mapping

    from sqlalchemy import ColumnElement, Delete, Update
    from sqlalchemy.orm import Session

    from backend.domain.entities.job import Job
    from backend.domain.ports.change_recorder import ChangeRecorder
    from backend.domain.value_objects.job_selection import JobSelection

_ACTIVE_STATUSES = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)
_QUEUE_ORDER = (JobModel.created_at.asc(), JobModel.id.asc())


class _KeyedBy(Enum):
    PHRASE = "phrase"
    WORD = "word"
    SOURCE = "source"


@dataclass(frozen=True)
class _Key:
    """What a job works on: its phrase, else its word, else its source."""

    job_type: str
    source_id: int
    candidate_id: int | None
    phrase_id: int | None

    @classmethod
    def of(cls, job: Job | JobModel) -> _Key:
        job_type = job.job_type if isinstance(job, JobModel) else job.job_type.value
        return cls(job_type, job.source_id, job.candidate_id, job.phrase_id)

    @property
    def keyed_by(self) -> tuple[_KeyedBy, int]:
        """What keys the job and its id there."""
        if self.phrase_id is not None:
            return _KeyedBy.PHRASE, self.phrase_id
        if self.candidate_id is not None:
            return _KeyedBy.WORD, self.candidate_id
        return _KeyedBy.SOURCE, self.source_id

    def same(self) -> ColumnElement[bool]:
        if self.phrase_id is not None:
            return and_(JobModel.job_type == self.job_type, JobModel.phrase_id == self.phrase_id)
        if self.candidate_id is not None:
            return and_(
                JobModel.job_type == self.job_type,
                JobModel.candidate_id == self.candidate_id,
                JobModel.phrase_id.is_(None),
            )
        return and_(
            JobModel.job_type == self.job_type,
            JobModel.source_id == self.source_id,
            JobModel.candidate_id.is_(None),
        )


def _by_column(keys: Iterable[_Key]) -> list[tuple[str, _KeyedBy, list[int]]]:
    """The keys grouped by job type and what keys them, with their ids there."""
    groups: dict[tuple[str, _KeyedBy], list[int]] = {}
    for key in keys:
        keyed_by, value = key.keyed_by
        groups.setdefault((key.job_type, keyed_by), []).append(value)
    return [(job_type, keyed_by, sorted(ids)) for (job_type, keyed_by), ids in groups.items()]


def _keyed_in(keyed_by: _KeyedBy, ids: Collection[int]) -> ColumnElement[bool]:
    """The jobs keyed by one of these ids: a word's job has no phrase, a source's job
    neither a word."""
    if keyed_by is _KeyedBy.PHRASE:
        return JobModel.phrase_id.in_(ids)
    if keyed_by is _KeyedBy.WORD:
        return and_(JobModel.candidate_id.in_(ids), JobModel.phrase_id.is_(None))
    return and_(JobModel.source_id.in_(ids), JobModel.candidate_id.is_(None))


def _selected(selection: JobSelection) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if selection.job_type is not None:
        clauses.append(JobModel.job_type == selection.job_type.value)
    if selection.source_id is not None:
        clauses.append(JobModel.source_id == selection.source_id)
    if selection.job_id is not None:
        clauses.append(JobModel.id == selection.job_id)
    if selection.error is not None:
        if selection.error == UNKNOWN_JOB_ERROR:
            clauses.append(or_(JobModel.error.is_(None), JobModel.error == UNKNOWN_JOB_ERROR))
        else:
            clauses.append(JobModel.error == selection.error)
    return clauses


class SqlaJobRepository(JobRepository):
    """SQLAlchemy implementation of JobRepository. A card shows what the queue holds for
    it: every write that adds, moves on or removes a job of a phrase records the phrase's
    content changed, of a word the word's."""

    def __init__(self, session: Session, recorder: ChangeRecorder) -> None:
        self._session = session
        self._recorder = recorder

    # ── Lifecycle ────────────────────────────────────────────────────

    def enqueue(self, jobs: list[Job]) -> list[Job]:
        """Set-based: the active keys, the failed jobs to supersede and the phrases, words
        and sources still there are each read in chunks, whatever the number of jobs. A
        job whose phrase, word or source is gone is left out."""
        unique: dict[_Key, Job] = {}
        for job in jobs:
            unique.setdefault(_Key.of(job), job)
        present = self._present(unique)
        keys = [key for key in unique if present(key)]
        active = self._active(keys)
        fresh = [key for key in keys if key not in active]
        self._drop_failed(fresh)
        models: list[JobModel] = []
        for key in fresh:
            model = JobModel.from_entity(unique[key])
            model.status = JobStatus.QUEUED.value
            model.error = None
            model.started_at = None
            models.append(model)
        self._session.add_all(models)
        self._session.flush()
        self._record_models(models)
        return [m.to_entity() for m in models]

    def _present(self, unique: Mapping[_Key, Job]) -> Callable[[_Key], bool]:
        """Whether the phrase, word and source of a key are still there."""
        found = {
            column: self._existing(model, [getattr(key, attribute) for key in unique])
            for column, model, attribute in (
                ("phrase", PhraseModel, "phrase_id"),
                ("word", StoredCandidateModel, "candidate_id"),
                ("source", SourceModel, "source_id"),
            )
        }
        return lambda key: (
            (key.phrase_id is None or key.phrase_id in found["phrase"])
            and (key.candidate_id is None or key.candidate_id in found["word"])
            and key.source_id in found["source"]
        )

    def _existing(
        self, model: type[PhraseModel | StoredCandidateModel | SourceModel],
        ids: Iterable[int | None],
    ) -> set[int]:
        wanted = sorted({i for i in ids if i is not None})
        return {
            found
            for chunk in chunks(wanted)
            for found in self._session.scalars(select(model.id).where(model.id.in_(chunk)))
        }

    def _active(self, keys: Collection[_Key]) -> set[_Key]:
        """The keys a queued or running job already works on."""
        return self._matching(keys, JobModel.status.in_(_ACTIVE_STATUSES))

    def _drop_failed(self, keys: Collection[_Key]) -> None:
        """The failed jobs of these keys go: a new job supersedes them."""
        failed = self._matching(keys, JobModel.status == JobStatus.FAILED.value)
        for job_type, keyed_by, ids in _by_column(failed):
            for chunk in chunks(ids):
                self._session.execute(delete(JobModel).where(
                    JobModel.job_type == job_type, _keyed_in(keyed_by, chunk),
                    JobModel.status == JobStatus.FAILED.value,
                ))

    def _matching(self, keys: Collection[_Key], status: ColumnElement[bool]) -> set[_Key]:
        """The keys a job in `status` works on, read a chunk of ids at a time."""
        wanted = {(key.job_type, *key.keyed_by): key for key in keys}
        found: set[_Key] = set()
        for job_type, keyed_by, ids in _by_column(keys):
            for chunk in chunks(ids):
                rows = self._session.execute(
                    select(
                        JobModel.job_type, JobModel.source_id, JobModel.candidate_id,
                        JobModel.phrase_id,
                    ).where(JobModel.job_type == job_type, _keyed_in(keyed_by, chunk), status),
                )
                for row in rows:
                    stored = _Key(row.job_type, row.source_id, row.candidate_id, row.phrase_id)
                    key = wanted.get((stored.job_type, *stored.keyed_by))
                    if key is not None:
                        found.add(key)
        return found

    def claim_next_run(
        self,
        run_limits: Mapping[JobType, int],
        accepted_types: frozenset[JobType] | None = None,
        mixed_source_types: frozenset[JobType] = frozenset(),
    ) -> list[Job]:
        fetch_size = max([DEFAULT_RUN_LIMIT, *run_limits.values()])
        stmt = (
            select(JobModel)
            .where(JobModel.status == JobStatus.QUEUED.value)
            .order_by(*_QUEUE_ORDER)
            .limit(fetch_size)
        )
        queued = list(self._session.execute(stmt).scalars().all())
        if not queued:
            return []
        head = queued[0]
        head_type = JobType(head.job_type)
        if accepted_types is not None and head_type not in accepted_types:
            return []

        run_limit = run_limits.get(head_type, DEFAULT_RUN_LIMIT)
        any_source = head_type in mixed_source_types
        run = list(takewhile(
            lambda m: m.job_type == head.job_type
            and (any_source or m.source_id == head.source_id),
            queued[:run_limit],
        ))
        now = datetime.now(tz=UTC)
        for model in run:
            model.status = JobStatus.RUNNING.value
            model.started_at = now
        self._session.flush()
        self._record_models(run)
        return [m.to_entity() for m in run]

    def still_claimed(self, jobs: list[Job]) -> set[int]:
        claimed_at = {j.id: j.started_at for j in jobs if j.id is not None}
        if not claimed_at:
            return set()
        stmt = select(JobModel.id, JobModel.started_at).where(
            JobModel.id.in_(list(claimed_at)), JobModel.status == JobStatus.RUNNING.value,
        )
        return {
            job_id for job_id, started_at in self._session.execute(stmt).all()
            if started_at is not None and started_at == claimed_at[job_id]
        }

    def complete(self, jobs: list[Job]) -> None:
        job_ids = [j.id for j in jobs if j.id is not None]
        if job_ids:
            self._session.execute(delete(JobModel).where(JobModel.id.in_(job_ids)))
        for job in jobs:
            self._session.execute(
                delete(JobModel).where(
                    _Key.of(job).same(), JobModel.status == JobStatus.FAILED.value,
                )
            )
        self._session.flush()
        self._record((job.phrase_id, job.candidate_id) for job in jobs)

    def fail(self, job_ids: list[int], error: str) -> None:
        if not job_ids:
            return
        self._affected(
            update(JobModel)
            .where(JobModel.id.in_(job_ids), JobModel.status == JobStatus.RUNNING.value)
            .values(status=JobStatus.FAILED.value, error=error)
        )

    def requeue_running(self) -> int:
        return self._affected(
            update(JobModel)
            .where(JobModel.status == JobStatus.RUNNING.value)
            .values(status=JobStatus.QUEUED.value, started_at=None)
        )

    def fail_running(self, job_type: JobType, error: str) -> int:
        return self._affected(
            update(JobModel)
            .where(
                JobModel.status == JobStatus.RUNNING.value,
                JobModel.job_type == job_type.value,
            )
            .values(status=JobStatus.FAILED.value, error=error)
        )

    # ── User actions ─────────────────────────────────────────────────

    def cancel(self, selection: JobSelection) -> int:
        return self._affected(
            delete(JobModel).where(JobModel.status.in_(_ACTIVE_STATUSES), *_selected(selection))
        )

    def cancel_for_phrases(self, phrase_ids: list[int]) -> int:
        cancelled = 0
        for chunk in chunks(phrase_ids):
            cancelled += self._affected(
                delete(JobModel).where(
                    JobModel.status.in_(_ACTIVE_STATUSES), JobModel.phrase_id.in_(chunk),
                )
            )
        return cancelled

    def dismiss(self, selection: JobSelection) -> int:
        return self._affected(
            delete(JobModel).where(
                JobModel.status == JobStatus.FAILED.value, *_selected(selection),
            )
        )

    def retry(self, selection: JobSelection) -> int:
        stmt = (
            select(JobModel)
            .where(JobModel.status == JobStatus.FAILED.value, *_selected(selection))
            .order_by(*_QUEUE_ORDER)
        )
        failed = list(self._session.execute(stmt).scalars().all())
        now = datetime.now(tz=UTC)
        retried = 0
        for model in failed:
            if self._is_active(_Key.of(model)):
                self._session.delete(model)
                continue
            model.status = JobStatus.QUEUED.value
            model.error = None
            model.started_at = None
            model.created_at = now
            retried += 1
        self._session.flush()
        self._record_models(failed)
        return retried

    # ── Reads ────────────────────────────────────────────────────────

    def get(self, job_id: int) -> Job | None:
        model = self._session.get(JobModel, job_id)
        return model.to_entity() if model is not None else None

    def sources_with_active_jobs(
        self, source_ids: Collection[int], job_types: frozenset[JobType],
    ) -> set[int]:
        return {
            source_id
            for chunk in chunks(sorted(source_ids))
            for source_id in self._session.scalars(
                select(JobModel.source_id)
                .where(
                    JobModel.source_id.in_(chunk),
                    JobModel.status.in_(_ACTIVE_STATUSES),
                    JobModel.job_type.in_([job_type.value for job_type in job_types]),
                )
                .distinct()
            )
        }

    def has_failed_matching(
        self, source_ids: Collection[int], job_type: JobType, marker: str,
    ) -> bool:
        """The phrase's job of the type is the failed one: no job of it is on its way."""
        active = aliased(JobModel)
        return any(
            self._session.execute(
                select(JobModel.id)
                .join(PhraseModel, PhraseModel.id == JobModel.phrase_id)
                .where(
                    JobModel.source_id.in_(chunk),
                    JobModel.job_type == job_type.value,
                    JobModel.status == JobStatus.FAILED.value,
                    JobModel.error.contains(marker, autoescape=True),
                    PhraseModel.shown_by.is_not(None),
                    ~exists().where(
                        active.phrase_id == JobModel.phrase_id,
                        active.job_type == JobModel.job_type,
                        active.status.in_(_ACTIVE_STATUSES),
                    ),
                )
                .limit(1)
            ).first() is not None
            for chunk in chunks(sorted(source_ids))
        )

    def has_active_jobs_for_source(
        self, source_id: int, job_types: frozenset[JobType] | None = None,
    ) -> bool:
        stmt = (
            select(func.count())
            .select_from(JobModel)
            .where(
                JobModel.source_id == source_id,
                JobModel.status.in_(_ACTIVE_STATUSES),
            )
        )
        if job_types is not None:
            stmt = stmt.where(
                JobModel.job_type.in_([jt.value for jt in job_types])
            )
        return self._session.execute(stmt).scalar_one() > 0

    def get_queue_summary(
        self, source_id: int | None = None,
    ) -> dict[str, dict[str, int]]:
        stmt = (
            select(
                JobModel.job_type,
                JobModel.status,
                func.count(),
            )
            .group_by(JobModel.job_type, JobModel.status)
        )
        if source_id is not None:
            stmt = stmt.where(JobModel.source_id == source_id)
        rows = self._session.execute(stmt).all()
        result: dict[str, dict[str, int]] = {
            jt.value: {"queued": 0, "running": 0, "failed": 0}
            for jt in JobType
        }
        for job_type_val, status_val, cnt in rows:
            if job_type_val in result and status_val in result[job_type_val]:
                result[job_type_val][status_val] = cnt
        return result

    def get_jobs_for_phrases(self, phrase_ids: list[int]) -> dict[int, dict[str, Job]]:
        result: dict[int, dict[str, Job]] = {}
        for chunk in chunks(phrase_ids):
            rows = self._session.scalars(
                select(JobModel)
                .where(JobModel.phrase_id.in_(chunk))
                .order_by(JobModel.status.asc())  # failed first: an active job wins
            )
            for model in rows:
                assert model.phrase_id is not None
                result.setdefault(model.phrase_id, {})[model.job_type] = model.to_entity()
        return result

    def get_jobs_for_candidates(
        self, candidate_ids: list[int],
    ) -> dict[int, dict[str, Job]]:
        result: dict[int, dict[str, Job]] = {}
        for chunk in chunks(candidate_ids):
            stmt = (
                select(JobModel)
                .where(JobModel.candidate_id.in_(chunk))
                .order_by(
                    # Order so that queued/running come last (we keep last per candidate_id+type)
                    JobModel.status.asc(),
                )
            )
            # Build mapping; later rows overwrite earlier ones per (candidate_id, job_type).
            # Status ordering: "failed" < "queued" < "running" (alphabetical asc)
            # So queued/running overwrite failed — which is the desired behavior.
            # A candidate's jobs all fall into its own chunk, so the order holds per candidate.
            for model in self._session.execute(stmt).scalars():
                if model.candidate_id is not None:
                    result.setdefault(model.candidate_id, {})[model.job_type] = model.to_entity()
        return result

    def get_jobs_by_status(
        self,
        statuses: list[JobStatus],
        source_id: int | None = None,
        job_type: JobType | None = None,
        limit: int | None = None,
    ) -> list[Job]:
        stmt = (
            select(JobModel)
            .where(JobModel.status.in_([s.value for s in statuses]))
            .order_by(*_QUEUE_ORDER)
        )
        if source_id is not None:
            stmt = stmt.where(JobModel.source_id == source_id)
        if job_type is not None:
            stmt = stmt.where(JobModel.job_type == job_type.value)
        if limit is not None:
            stmt = stmt.limit(limit)
        models = self._session.execute(stmt).scalars().all()
        return [m.to_entity() for m in models]

    def get_failed_grouped_by_error(
        self,
        source_id: int | None = None,
        job_type: JobType | None = None,
    ) -> list[FailedJobGroup]:
        error = func.coalesce(JobModel.error, UNKNOWN_JOB_ERROR)
        stmt = (
            select(
                JobModel.job_type,
                error.label("error"),
                func.count().label("count"),
                func.group_concat(JobModel.source_id).label("source_ids_csv"),
            )
            .where(JobModel.status == JobStatus.FAILED.value)
            .group_by(JobModel.job_type, error)
            .order_by(func.count().desc())
        )
        if source_id is not None:
            stmt = stmt.where(JobModel.source_id == source_id)
        if job_type is not None:
            stmt = stmt.where(JobModel.job_type == job_type.value)

        return [
            FailedJobGroup(
                job_type=JobType(row.job_type),
                error=row.error,
                count=row._mapping["count"],
                source_counts=dict(Counter(
                    int(s) for s in str(row.source_ids_csv or "").split(",") if s
                )),
            )
            for row in self._session.execute(stmt).all()
        ]

    # ── Helpers ──────────────────────────────────────────────────────

    def _is_active(self, key: _Key) -> bool:
        stmt = (
            select(func.count())
            .select_from(JobModel)
            .where(key.same(), JobModel.status.in_(_ACTIVE_STATUSES))
        )
        return self._session.execute(stmt).scalar_one() > 0

    def _affected(self, stmt: Update | Delete) -> int:
        """Runs the write; records what the jobs it touched work on and counts them."""
        rows = self._session.execute(
            stmt.returning(JobModel.phrase_id, JobModel.candidate_id),
        ).all()
        self._session.flush()
        self._record((phrase_id, word_id) for phrase_id, word_id in rows)
        return len(rows)

    def _record_models(self, models: Iterable[JobModel]) -> None:
        self._record((model.phrase_id, model.candidate_id) for model in models)

    def _record(self, keys: Iterable[tuple[int | None, int | None]]) -> None:
        """A job of a phrase changes what its card shows; a job of a word, its cards'."""
        for phrase_id, word_id in keys:
            if phrase_id is not None:
                self._recorder.record(CardContentChanged(phrase_id))
            elif word_id is not None:
                self._recorder.record(WordContentChanged(word_id))
