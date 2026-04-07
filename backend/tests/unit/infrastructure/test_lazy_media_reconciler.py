from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.services.lazy_media_reconciler import LazyMediaReconciler


@pytest.mark.unit
@pytest.mark.asyncio
class TestLazyMediaReconciler:
    async def test_schedule_runs_reconcile_in_background(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)

        session_factory = MagicMock()
        session = MagicMock()
        session_factory.return_value = session

        candidate = MagicMock()
        candidate.id = 10
        candidate.source_id = 1
        candidate.screenshot_path = str(media_root / "1" / "10_screenshot.webp")  # file does NOT exist
        candidate.audio_path = None

        with patch("backend.infrastructure.services.lazy_media_reconciler.SqlaCandidateRepository") as cand_cls:
            repo = cand_cls.return_value
            repo.get_by_source.return_value = [candidate]
            reconciler = LazyMediaReconciler(session_factory, str(media_root))

            await reconciler.schedule(1)
            # Give background task time to run
            await asyncio.sleep(0.1)

            repo.clear_media_path.assert_called_once_with(
                10, clear_screenshot=True, clear_audio=False
            )
            session.commit.assert_called_once()
            session.close.assert_called_once()

    async def test_schedule_dedupes_concurrent_requests(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        call_count = 0
        release = asyncio.Event()

        async def slow_reconcile(sid: int) -> None:
            nonlocal call_count
            call_count += 1
            await release.wait()

        session_factory = MagicMock()
        reconciler = LazyMediaReconciler(session_factory, str(media_root))
        # Monkey-patch the internal worker
        reconciler._reconcile_source = slow_reconcile  # type: ignore[assignment,method-assign]

        await reconciler.schedule(1)
        await reconciler.schedule(1)
        await reconciler.schedule(1)
        await asyncio.sleep(0.02)
        release.set()
        await asyncio.sleep(0.05)

        assert call_count == 1  # dedup worked

    async def test_different_source_ids_run_independently(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        call_log: list[int] = []
        release = asyncio.Event()

        async def slow_reconcile(sid: int) -> None:
            call_log.append(sid)
            await release.wait()

        session_factory = MagicMock()
        reconciler = LazyMediaReconciler(session_factory, str(media_root))
        reconciler._reconcile_source = slow_reconcile  # type: ignore[assignment,method-assign]

        await reconciler.schedule(1)
        await reconciler.schedule(2)
        await asyncio.sleep(0.02)
        release.set()
        await asyncio.sleep(0.05)

        assert sorted(call_log) == [1, 2]
