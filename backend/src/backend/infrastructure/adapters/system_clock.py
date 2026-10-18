from __future__ import annotations

from datetime import UTC, datetime

from backend.domain.ports.clock import Clock


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(tz=UTC)
