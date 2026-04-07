from __future__ import annotations

from enum import Enum


class EnrichmentStatus(Enum):
    """Lifecycle status for an enrichment (meaning or media) of a candidate.

    QUEUED: enqueued in worker, not yet picked up.
    RUNNING: currently being generated (or between automatic retries).
    DONE: successfully generated, payload available.
    FAILED: all retries exhausted or permanent error; `error` field has the reason.
    """

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
