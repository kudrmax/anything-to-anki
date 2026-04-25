from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.domain.value_objects.bootstrap_index_status import BootstrapIndexStatus


@dataclass(frozen=True)
class BootstrapIndexMeta:
    """Metadata about the bootstrap calibration data build."""

    status: BootstrapIndexStatus
    error: str | None
    built_at: datetime | None
    word_count: int
