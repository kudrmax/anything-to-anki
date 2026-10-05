"""DTOs for queue management endpoints."""
from __future__ import annotations

from pydantic import BaseModel


class JobTypeCountsDTO(BaseModel):
    job_type: str
    queued: int
    running: int
    failed: int


class QueueJobDTO(BaseModel):
    job_id: int
    job_type: str
    source_id: int
    source_title: str
    status: str  # "running" | "queued"
    position: int | None
    candidate_id: int | None


class FailedSourceDTO(BaseModel):
    source_id: int
    source_title: str
    count: int


class FailedGroupDTO(BaseModel):
    error_text: str
    count: int
    sources: list[FailedSourceDTO]


class FailedByJobTypeDTO(BaseModel):
    job_type: str
    total_failed: int
    groups: list[FailedGroupDTO]


class QueueSnapshotDTO(BaseModel):
    """Everything the queue screen shows, in one read.

    ``counts`` lists only job types with any jobs, in pipeline order.
    ``queued`` holds the first jobs in line; ``total_queued`` counts them all.
    """

    counts: list[JobTypeCountsDTO]
    total_queued: int
    total_running: int
    total_failed: int
    running: list[QueueJobDTO]
    queued: list[QueueJobDTO]
    failed: list[FailedByJobTypeDTO]


class QueueActionRequestDTO(BaseModel):
    """Which jobs a queue action applies to. Every unset field matches everything."""

    job_type: str | None = None
    source_id: int | None = None
    job_id: int | None = None
    error_text: str | None = None


class QueueActionResultDTO(BaseModel):
    affected: int
