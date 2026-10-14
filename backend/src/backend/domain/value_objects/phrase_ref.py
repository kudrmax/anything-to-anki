from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhraseRef:
    """The phrase a job works on, at the revision of its text the job was queued for."""

    phrase_id: int
    revision: int
