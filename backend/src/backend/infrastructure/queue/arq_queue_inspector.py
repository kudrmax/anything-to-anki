"""ArqQueueInspector — implementation of QueueInspectorPort backed by arq/Redis."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from backend.domain.ports.queue_inspector import QueueInspectorPort
from backend.domain.value_objects.queued_job_info import QueuedJobInfo

if TYPE_CHECKING:
    from arq.connections import ArqRedis

_ARQ_QUEUE_KEY = "arq:queue"
_ARQ_IN_PROGRESS_KEY = "arq:in-progress"
_ARQ_ABORT_KEY = "arq:abort_jobs"
_SCORE_MIN = "-inf"
_SCORE_MAX = "+inf"


def parse_job_id(job_id: str) -> tuple[str, int | None, int | None] | None:
    """Parse arq job_id into (job_type, source_id, candidate_id).

    Returns None if format is unrecognised.
    source_id is set for meaning/youtube jobs (encoded in job_id).
    candidate_id is set for media/pronunciation jobs.
    """
    parts = job_id.split("_")
    if len(parts) < 2:
        return None
    prefix = parts[0]
    try:
        if prefix == "meaning" and len(parts) >= 4:
            return ("meanings", int(parts[1]), None)
        if prefix == "media" and len(parts) >= 3:
            # New format: media_{source_id}_{candidate_id}_{ts}
            return ("media", int(parts[1]), int(parts[2]))
        if prefix == "pronunciation" and len(parts) >= 3:
            # New format: pronunciation_{source_id}_{candidate_id}_{ts}
            return ("pronunciation", int(parts[1]), int(parts[2]))
        if prefix == "youtube":
            return ("youtube_dl", int(parts[1]), None)
    except (ValueError, IndexError):
        return None
    return None


def _decode(value: bytes | str) -> str:
    """Decode bytes from Redis to str."""
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


class ArqQueueInspector(QueueInspectorPort):
    """Inspects arq job queue via direct Redis commands."""

    def __init__(
        self,
        redis: ArqRedis,
        candidate_source_map: dict[int, int] | None = None,
    ) -> None:
        self._redis = redis
        self._candidate_source_map: dict[int, int] = candidate_source_map or {}

    def _resolve_source_id(
        self,
        job_type: str,
        source_id: int | None,
        candidate_id: int | None,
    ) -> int | None:
        """Return source_id for a job, resolving via candidate map when needed."""
        if source_id is not None:
            return source_id
        if candidate_id is not None and job_type in ("media", "pronunciation"):
            return self._candidate_source_map.get(candidate_id)
        return None

    async def get_queued_jobs(
        self,
        source_id: int | None = None,
        limit: int = 50,
    ) -> list[QueuedJobInfo]:
        """Return queued jobs ordered by FIFO position (ascending score)."""
        raw: list[tuple[bytes | str, float]] = await self._redis.zrangebyscore(
            _ARQ_QUEUE_KEY,
            _SCORE_MIN,
            _SCORE_MAX,
            withscores=True,
        )
        results: list[QueuedJobInfo] = []
        position = 0
        for item, score in raw:
            job_id_str = _decode(item)
            parsed = parse_job_id(job_id_str)
            if parsed is None:
                continue
            job_type, jid_source_id, candidate_id = parsed
            resolved = self._resolve_source_id(job_type, jid_source_id, candidate_id)
            if source_id is not None and resolved != source_id:
                position += 1
                continue
            if resolved is None:
                position += 1
                continue
            results.append(
                QueuedJobInfo(
                    job_id=job_id_str,
                    job_type=job_type,
                    source_id=resolved,
                    position=position,
                    scheduled_at=score,
                )
            )
            position += 1
            if len(results) >= limit:
                break
        return results

    async def get_running_jobs(
        self,
        source_id: int | None = None,
    ) -> list[QueuedJobInfo]:
        """Return currently running jobs."""
        raw: set[bytes | str] = cast(
            "set[bytes | str]",
            await cast("Any", self._redis.smembers(_ARQ_IN_PROGRESS_KEY)),
        )
        results: list[QueuedJobInfo] = []
        for item in raw:
            job_id_str = _decode(item)
            parsed = parse_job_id(job_id_str)
            if parsed is None:
                continue
            job_type, jid_source_id, candidate_id = parsed
            resolved = self._resolve_source_id(job_type, jid_source_id, candidate_id)
            if source_id is not None and resolved != source_id:
                continue
            if resolved is None:
                continue
            results.append(
                QueuedJobInfo(
                    job_id=job_id_str,
                    job_type=job_type,
                    source_id=resolved,
                    position=None,
                    scheduled_at=0.0,
                )
            )
        return results

    async def get_total_queued(self) -> int:
        """Return total number of queued jobs (unfiltered)."""
        count: int = await self._redis.zcard(_ARQ_QUEUE_KEY)
        return count

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a specific job by ID. Returns True if was in queue."""
        removed: int = await self._redis.zrem(_ARQ_QUEUE_KEY, job_id)
        if removed:
            await self._redis.zadd(_ARQ_ABORT_KEY, {job_id: 1})
            return True
        return False

    async def cancel_jobs_by_type(
        self,
        job_type: str,
        source_id: int | None = None,
    ) -> int:
        """Cancel all queued jobs of a given type. Returns count cancelled."""
        raw: list[bytes | str] = await self._redis.zrangebyscore(
            _ARQ_QUEUE_KEY,
            _SCORE_MIN,
            _SCORE_MAX,
        )
        cancelled = 0
        for item in raw:
            job_id_str = _decode(item)
            parsed = parse_job_id(job_id_str)
            if parsed is None:
                continue
            jt, jid_source_id, candidate_id = parsed
            if jt != job_type:
                continue
            if source_id is not None:
                resolved = self._resolve_source_id(jt, jid_source_id, candidate_id)
                if resolved != source_id:
                    continue
            removed: int = await self._redis.zrem(_ARQ_QUEUE_KEY, job_id_str)
            if removed:
                await self._redis.zadd(_ARQ_ABORT_KEY, {job_id_str: 1})
                cancelled += 1
        return cancelled
