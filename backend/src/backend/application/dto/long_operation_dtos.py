from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from backend.domain.value_objects.long_operation_kind import LongOperationKind  # noqa: TC001


class LongOperationOutcome(Enum):
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
    FAILED = "failed"


class LongOperationStatusDTO(BaseModel):
    """Whether a long operation runs and how far; once it ends, how it ended.
    `operation_id` grows with each operation started, so a new outcome tells from an old
    one. `kind` is that of the last operation started; None before any."""

    operation_id: int
    kind: LongOperationKind | None
    running: bool
    percent: int
    cancellable: bool
    outcome: LongOperationOutcome | None
    error: str | None
