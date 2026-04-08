from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import TYPE_CHECKING

from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_FILENAME_PATTERN = re.compile(r"^(\d+)_(screenshot|audio)\.")


class LazyMediaReconciler:
    """Background reconciler triggered when a SPECIFIC media file 404s at runtime.

    Each call clears EXACTLY ONE candidate's ONE field (screenshot or audio).
    The deduplication key is `(source_id, filename)` so concurrent 404s for the
    same file collapse into one task, but unrelated 404s run independently.

    History note: an earlier version took just a `source_id` and bulk-iterated
    every candidate of that source, calling `clear_paths` for every file
    missing on disk. That turned out to be catastrophically destructive — a
    single 404 (often from a transient race condition) could nullify metadata
    for hundreds of unrelated candidates. The per-file scope below makes the
    blast radius equal to the user's actual loss.
    """

    def __init__(self, session_factory: sessionmaker[Session], media_root: str) -> None:
        self._session_factory = session_factory
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
        m = _FILENAME_PATTERN.match(filename)
        if not m:
            return  # unknown filename shape — leave the DB alone
        candidate_id = int(m.group(1))
        kind = m.group(2)

        # Race protection: maybe the file appeared between the route's check
        # and our async task running. Re-stat before clearing.
        full = os.path.join(self._media_root, str(source_id), filename)
        if os.path.exists(full):
            return

        session = self._session_factory()
        try:
            media_repo = SqlaCandidateMediaRepository(session)
            media_repo.clear_paths(
                candidate_id,
                clear_screenshot=(kind == "screenshot"),
                clear_audio=(kind == "audio"),
            )
            session.commit()
            logger.warning(
                "LazyReconcile: cleared %s_path for candidate %d "
                "(source %d, file %s missing)",
                kind, candidate_id, source_id, full,
            )
        finally:
            session.close()
