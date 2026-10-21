"""Writes every change of a phrase's text or results goes through."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select, update

from backend.domain.value_objects.job_status import JobStatus
from backend.infrastructure.persistence.models import (
    CandidateMediaModel,
    CandidateTTSModel,
    JobModel,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from sqlalchemy.orm import Session

# Made of the phrase's exact text, besides the polish on the phrase itself.
TEXT_RESULT_MODELS = (CandidateMediaModel, CandidateTTSModel)
# Ids per `IN (…)`: well under SQLite's limit of bound parameters.
SQL_IN_CHUNK = 500


def chunks[T](ids: Sequence[T]) -> Iterator[list[T]]:
    for start in range(0, len(ids), SQL_IN_CHUNK):
        yield list(ids[start:start + SQL_IN_CHUNK])


def files_of(session: Session, phrase_ids: Sequence[int]) -> list[str]:
    """The video frames, clips and TTS files of the phrases."""
    files: list[str] = []
    for chunk in chunks(phrase_ids):
        for shot, clip in session.execute(
            select(CandidateMediaModel.screenshot_path, CandidateMediaModel.audio_path)
            .where(CandidateMediaModel.phrase_id.in_(chunk))
        ):
            files.extend(path for path in (shot, clip) if path)
        files.extend(
            path for path in session.scalars(
                select(CandidateTTSModel.audio_path).where(CandidateTTSModel.phrase_id.in_(chunk))
            ) if path
        )
    return files


def drop_text_results(session: Session, phrase_ids: Sequence[int]) -> None:
    """What was made of the phrases' exact text, besides the polish on the phrase."""
    for chunk in chunks(phrase_ids):
        for model in TEXT_RESULT_MODELS:
            session.execute(delete(model).where(model.phrase_id.in_(chunk)))


def queued_jobs_follow(session: Session, phrase_id: int, revision: int) -> None:
    """Queued jobs read the phrase when they run, so they work on the new text."""
    session.execute(
        update(JobModel)
        .where(JobModel.phrase_id == phrase_id, JobModel.status == JobStatus.QUEUED.value)
        .values(phrase_revision=revision)
        .execution_options(synchronize_session=False)
    )


def cancel_running_jobs(session: Session, phrase_ids: Sequence[int]) -> None:
    """A running job works on the text it read: once the text changes, its result is
    stale."""
    for chunk in chunks(phrase_ids):
        session.execute(
            delete(JobModel).where(
                JobModel.status == JobStatus.RUNNING.value, JobModel.phrase_id.in_(chunk),
            )
        )
