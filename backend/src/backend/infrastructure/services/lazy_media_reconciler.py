from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import TYPE_CHECKING

from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)

if TYPE_CHECKING:
    from backend.infrastructure.persistence.session_work import SessionWork

logger = logging.getLogger(__name__)

_FILENAME_PATTERN = re.compile(r"^p?\d+_(screenshot|audio)\.")


class LazyMediaReconciler:
    """Background reconciler triggered when a SPECIFIC media file 404s at runtime.

    Each call clears EXACTLY the media fields that point at the ONE missing file, by
    their path value — whichever phrase they belong to.
    The deduplication key is `(source_id, filename)` so concurrent 404s for the
    same file collapse into one task, but unrelated 404s run independently.

    History note: an earlier version took just a `source_id` and bulk-iterated
    every candidate of that source, calling `clear_paths` for every file
    missing on disk. That turned out to be catastrophically destructive — a
    single 404 (often from a transient race condition) could nullify metadata
    for hundreds of unrelated candidates. The per-file scope below makes the
    blast radius equal to the user's actual loss.
    """

    def __init__(self, work: SessionWork, media_root: str) -> None:
        self._work = work
        self._media_root = media_root
        self._in_progress: set[tuple[int, str]] = set()
        self._lock = asyncio.Lock()

    async def schedule(self, source_id: int, filename: str) -> None:
        key = (source_id, filename)
        async with self._lock:
            if key in self._in_progress:
                return
            self._in_progress.add(key)
        asyncio.create_task(self._wrap(source_id, filename))

    async def _wrap(self, source_id: int, filename: str) -> None:
        try:
            await self._reconcile_one(source_id, filename)
        except Exception:
            logger.exception(
                "LazyReconcile source=%d file=%s failed", source_id, filename,
            )
        finally:
            async with self._lock:
                self._in_progress.discard((source_id, filename))

    async def _reconcile_one(self, source_id: int, filename: str) -> None:
        # Offload blocking file I/O and DB access to a thread
        await asyncio.to_thread(self._reconcile_sync, source_id, filename)

    def _reconcile_sync(self, source_id: int, filename: str) -> None:
        if not _FILENAME_PATTERN.match(filename):
            return  # unknown filename shape — leave the DB alone

        # Race protection: maybe the file appeared between the route's check
        # and our async task running. Re-stat before clearing.
        full = os.path.join(self._media_root, str(source_id), filename)
        if os.path.exists(full):
            return

        self._work.write(
            lambda session: SqlaCandidateMediaRepository(
                session, SessionChangeRecorder(session),
            ).clear_missing_file(full),
        )
        logger.warning(
            "LazyReconcile: cleared the rows pointing at %s (source %d, file missing)",
            full, source_id,
        )
