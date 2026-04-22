"""DTOs for queue management endpoints."""
from __future__ import annotations

from pydantic import BaseModel


class JobTypeSummaryDTO(BaseModel):
    queued: int
    running: int
    failed: int


class QueueGlobalSummaryDTO(BaseModel):
    meaning: JobTypeSummaryDTO
    media: JobTypeSummaryDTO
    pronunciation: JobTypeSummaryDTO
    video_download: JobTypeSummaryDTO


class QueueJobDTO(BaseModel):
    job_id: int
    job_type: str
    source_id: int
    source_title: str
    status: str  # "running" | "queued"
    position: int | None
    candidate_id: int | None


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
    job_id: int | None = None
