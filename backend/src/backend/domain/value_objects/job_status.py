from __future__ import annotations

from enum import Enum


class JobStatus(Enum):
    """Status of a job in the queue.

    Only three states: the jobs table is a QUEUE, not a log.
    - DONE jobs are deleted (result is in enrichment tables).
    - CANCELLED jobs are deleted (nothing to show).
    - FAILED jobs stay (for user to see error + retry).
    """

    QUEUED = "queued"
    RUNNING = "running"
    FAILED = "failed"
