from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class AIOutage:
    """The AI answers no request: AI work waits in the queue until it is back."""

    reason: str
    since: datetime
