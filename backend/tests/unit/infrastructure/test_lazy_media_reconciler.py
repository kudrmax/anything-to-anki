from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.services.lazy_media_reconciler import LazyMediaReconciler


@pytest.mark.unit
@pytest.mark.asyncio
class TestLazyMediaReconciler:
    async def test_clears_specified_screenshot_only(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        # File does NOT exist on disk → reconciler should clear

        session_factory = MagicMock()
        session = MagicMock()
        session_factory.return_value = session

        with patch(
            "backend.infrastructure.services.lazy_media_reconciler.SqlaCandidateMediaRepository"
        ) as media_cls:
            media_repo = media_cls.return_value
            reconciler = LazyMediaReconciler(session_factory, str(media_root))

            await reconciler.schedule(1, "10_screenshot.webp")
            await asyncio.sleep(0.1)

            media_repo.clear_paths.assert_called_once_with(
                10, clear_screenshot=True, clear_audio=False,
            )
            session.commit.assert_called_once()
            session.close.assert_called_once()

    async def test_clears_specified_audio_only(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)

        session_factory = MagicMock()
        session = MagicMock()
        session_factory.return_value = session

        with patch(
            "backend.infrastructure.services.lazy_media_reconciler.SqlaCandidateMediaRepository"
        ) as media_cls:
            media_repo = media_cls.return_value
            reconciler = LazyMediaReconciler(session_factory, str(media_root))

            await reconciler.schedule(1, "42_audio.m4a")
            await asyncio.sleep(0.1)

            media_repo.clear_paths.assert_called_once_with(
                42, clear_screenshot=False, clear_audio=True,
            )

    async def test_noop_when_file_reappears(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        # Race protection: file exists at reconcile time → no clear
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        (media_root / "1" / "10_screenshot.webp").write_bytes(b"fake")

        session_factory = MagicMock()
        session = MagicMock()
        session_factory.return_value = session

        with patch(
            "backend.infrastructure.services.lazy_media_reconciler.SqlaCandidateMediaRepository"
        ) as media_cls:
            media_repo = media_cls.return_value
            reconciler = LazyMediaReconciler(session_factory, str(media_root))

            await reconciler.schedule(1, "10_screenshot.webp")
            await asyncio.sleep(0.1)

            media_repo.clear_paths.assert_not_called()
            session.commit.assert_not_called()

    async def test_ignores_unknown_filename_shape(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)

        session_factory = MagicMock()
        session = MagicMock()
        session_factory.return_value = session

        with patch(
            "backend.infrastructure.services.lazy_media_reconciler.SqlaCandidateMediaRepository"
        ) as media_cls:
            media_repo = media_cls.return_value
            reconciler = LazyMediaReconciler(session_factory, str(media_root))

            await reconciler.schedule(1, "weird.txt")
            await asyncio.sleep(0.1)

            media_repo.clear_paths.assert_not_called()

    async def test_dedupes_concurrent_requests_for_same_file(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        call_count = 0
        release = asyncio.Event()

        async def slow_reconcile(source_id: int, filename: str) -> None:
            nonlocal call_count
            call_count += 1
            await release.wait()

        session_factory = MagicMock()
        reconciler = LazyMediaReconciler(session_factory, str(media_root))
        # Monkey-patch the internal worker
        reconciler._reconcile_one = slow_reconcile  # type: ignore[assignment,method-assign]

        await reconciler.schedule(1, "10_screenshot.webp")
        await reconciler.schedule(1, "10_screenshot.webp")
        await reconciler.schedule(1, "10_screenshot.webp")
        await asyncio.sleep(0.02)
        release.set()
        await asyncio.sleep(0.05)

        assert call_count == 1  # dedup worked

    async def test_different_files_run_independently(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        call_log: list[tuple[int, str]] = []
        release = asyncio.Event()

        async def slow_reconcile(source_id: int, filename: str) -> None:
            call_log.append((source_id, filename))
            await release.wait()

        session_factory = MagicMock()
        reconciler = LazyMediaReconciler(session_factory, str(media_root))
        reconciler._reconcile_one = slow_reconcile  # type: ignore[assignment,method-assign]

        await reconciler.schedule(1, "10_screenshot.webp")
        await reconciler.schedule(1, "11_screenshot.webp")
        await reconciler.schedule(2, "10_screenshot.webp")
        await asyncio.sleep(0.02)
        release.set()
        await asyncio.sleep(0.05)

        assert sorted(call_log) == [(1, "10_screenshot.webp"), (1, "11_screenshot.webp"), (2, "10_screenshot.webp")]
