from __future__ import annotations

from enum import Enum


class EnrichmentStatus(Enum):
    """Lifecycle status for an enrichment (meaning or media) of a candidate.

    IDLE: row exists with prep data (e.g. media timecodes), no activity yet.
        Awaiting user action ("Generate Media" / "Generate Meanings" click).
    QUEUED: enqueued in worker, not yet picked up.
    RUNNING: currently being generated (or between automatic retries).
    DONE: successfully generated, payload available.
    FAILED: all retries exhausted or permanent error; `error` field has the reason.
    """

    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
