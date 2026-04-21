"""DTOs for queue management endpoints."""
from __future__ import annotations

from pydantic import BaseModel


class JobTypeSummaryDTO(BaseModel):
    queued: int
    running: int
    failed: int


class QueueGlobalSummaryDTO(BaseModel):
    youtube_dl: JobTypeSummaryDTO
    processing: JobTypeSummaryDTO
    meanings: JobTypeSummaryDTO
    media: JobTypeSummaryDTO
    pronunciation: JobTypeSummaryDTO


class QueueJobDTO(BaseModel):
    job_id: str
    job_type: str
    source_id: int
    source_title: str
    status: str
    position: int | None
    substage: str | None


class QueueOrderDTO(BaseModel):
    running: list[QueueJobDTO]
    queued: list[QueueJobDTO]
    total_queued: int


class FailedSourceDTO(BaseModel):
    source_id: int
    source_title: str
    count: int


class FailedGroupDTO(BaseModel):
    error_text: str
    count: int
    sources: list[FailedSourceDTO]
    candidate_ids: list[int]


class FailedByJobTypeDTO(BaseModel):
    job_type: str
    total_failed: int
    groups: list[FailedGroupDTO]


class QueueFailedDTO(BaseModel):
    types: list[FailedByJobTypeDTO]


class RetryRequestDTO(BaseModel):
    job_type: str
    source_id: int | None = None
    error_text: str | None = None


class CancelRequestDTO(BaseModel):
    job_type: str
    source_id: int | None = None
    job_id: str | None = None
