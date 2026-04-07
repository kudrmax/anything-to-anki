from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)


class LazyMediaReconciler:
    """Background reconciliation triggered when a media file 404s at runtime.

    Deduplicates per source_id so concurrent 404s from the same source
    don't spawn multiple reconciliation tasks.
    """

    def __init__(self, session_factory: sessionmaker[Session], media_root: str) -> None:
        self._session_factory = session_factory
        self._media_root = media_root
        self._in_progress: set[int] = set()
        self._lock = asyncio.Lock()

    async def schedule(self, source_id: int) -> None:
        async with self._lock:
            if source_id in self._in_progress:
                return
            self._in_progress.add(source_id)
        asyncio.create_task(self._wrap(source_id))

    async def _wrap(self, source_id: int) -> None:
        try:
            await self._reconcile_source(source_id)
        except Exception:
            logger.exception("LazyReconcile source=%d failed", source_id)
        finally:
            async with self._lock:
                self._in_progress.discard(source_id)

    async def _reconcile_source(self, source_id: int) -> None:
        # Offload blocking file I/O and DB access to a thread
        await asyncio.to_thread(self._reconcile_sync, source_id)

    def _reconcile_sync(self, source_id: int) -> None:
        session = self._session_factory()
        try:
            repo = SqlaCandidateRepository(session)
            candidates = repo.get_by_source(source_id)
            cleared_shot = 0
            cleared_audio = 0
            for c in candidates:
                if c.id is None:
                    continue
                missing_shot = c.screenshot_path is not None and not os.path.exists(c.screenshot_path)
                missing_audio = c.audio_path is not None and not os.path.exists(c.audio_path)
                if missing_shot or missing_audio:
                    repo.clear_media_path(
                        c.id,
                        clear_screenshot=missing_shot,
                        clear_audio=missing_audio,
                    )
                    if missing_shot:
                        cleared_shot += 1
                    if missing_audio:
                        cleared_audio += 1
            session.commit()
            logger.info(
                "LazyReconcile source=%d: cleared %d screenshot, %d audio",
                source_id, cleared_shot, cleared_audio,
            )
        finally:
            session.close()
