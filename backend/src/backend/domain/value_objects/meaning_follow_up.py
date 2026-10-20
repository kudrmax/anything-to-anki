from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MeaningFollowUp:
    """What the user asked about a phrase's meaning: a preset action, or their own question."""

    action: str
    text: str | None = None
