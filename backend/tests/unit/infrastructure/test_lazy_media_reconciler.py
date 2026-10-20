from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from backend.infrastructure.persistence.session_work import SessionWork
from backend.infrastructure.services.lazy_media_reconciler import LazyMediaReconciler

if TYPE_CHECKING:
    from pathlib import Path


def _work() -> tuple[SessionWork, MagicMock]:
    unit_of_work = MagicMock()
    return SessionWork(MagicMock(), lambda _session: unit_of_work), unit_of_work


@pytest.mark.unit
@pytest.mark.asyncio
class TestLazyMediaReconciler:
    async def test_clears_specified_screenshot_only(self, tmp_path: Path) -> None:
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        # File does NOT exist on disk → reconciler should clear

        work, unit_of_work = _work()

        with patch(
            "backend.infrastructure.services.lazy_media_reconciler.SqlaCandidateMediaRepository"
        ) as media_cls:
            media_repo = media_cls.return_value
            reconciler = LazyMediaReconciler(work, str(media_root))

            await reconciler.schedule(1, "10_screenshot.webp")
            await asyncio.sleep(0.1)

            media_repo.clear_missing_file.assert_called_once_with(
                str(media_root / "1" / "10_screenshot.webp"),
            )
            unit_of_work.write.assert_called_once()

    async def test_clears_specified_audio_only(self, tmp_path: Path) -> None:
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)

        work, unit_of_work = _work()

        with patch(
            "backend.infrastructure.services.lazy_media_reconciler.SqlaCandidateMediaRepository"
        ) as media_cls:
            media_repo = media_cls.return_value
            reconciler = LazyMediaReconciler(work, str(media_root))

            await reconciler.schedule(1, "42_audio.m4a")
            await asyncio.sleep(0.1)

            media_repo.clear_missing_file.assert_called_once_with(
                str(media_root / "1" / "42_audio.m4a"),
            )

    async def test_noop_when_file_reappears(self, tmp_path: Path) -> None:
        # Race protection: file exists at reconcile time → no clear
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        (media_root / "1" / "10_screenshot.webp").write_bytes(b"fake")

        work, unit_of_work = _work()

        with patch(
            "backend.infrastructure.services.lazy_media_reconciler.SqlaCandidateMediaRepository"
        ) as media_cls:
            media_repo = media_cls.return_value
            reconciler = LazyMediaReconciler(work, str(media_root))

            await reconciler.schedule(1, "10_screenshot.webp")
            await asyncio.sleep(0.1)

            media_repo.clear_missing_file.assert_not_called()
            unit_of_work.write.assert_not_called()

    async def test_ignores_unknown_filename_shape(self, tmp_path: Path) -> None:
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)

        work, unit_of_work = _work()

        with patch(
            "backend.infrastructure.services.lazy_media_reconciler.SqlaCandidateMediaRepository"
        ) as media_cls:
            media_repo = media_cls.return_value
            reconciler = LazyMediaReconciler(work, str(media_root))

            await reconciler.schedule(1, "weird.txt")
            await asyncio.sleep(0.1)

            media_repo.clear_missing_file.assert_not_called()

    async def test_dedupes_concurrent_requests_for_same_file(self, tmp_path: Path) -> None:
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        call_count = 0
        release = asyncio.Event()

        async def slow_reconcile(source_id: int, filename: str) -> None:
            nonlocal call_count
            call_count += 1
            await release.wait()

        work, _ = _work()
        reconciler = LazyMediaReconciler(work, str(media_root))
        # Monkey-patch the internal worker
        reconciler._reconcile_one = slow_reconcile  # type: ignore[assignment,method-assign]

        await reconciler.schedule(1, "10_screenshot.webp")
        await reconciler.schedule(1, "10_screenshot.webp")
        await reconciler.schedule(1, "10_screenshot.webp")
        await asyncio.sleep(0.02)
        release.set()
        await asyncio.sleep(0.05)

        assert call_count == 1  # dedup worked

    async def test_different_files_run_independently(self, tmp_path: Path) -> None:
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        call_log: list[tuple[int, str]] = []
        release = asyncio.Event()

        async def slow_reconcile(source_id: int, filename: str) -> None:
            call_log.append((source_id, filename))
            await release.wait()

        work, _ = _work()
        reconciler = LazyMediaReconciler(work, str(media_root))
        reconciler._reconcile_one = slow_reconcile  # type: ignore[assignment,method-assign]

        await reconciler.schedule(1, "10_screenshot.webp")
        await reconciler.schedule(1, "11_screenshot.webp")
        await reconciler.schedule(2, "10_screenshot.webp")
        await asyncio.sleep(0.02)
        release.set()
        await asyncio.sleep(0.05)

        assert sorted(call_log) == [
            (1, "10_screenshot.webp"),
            (1, "11_screenshot.webp"),
            (2, "10_screenshot.webp"),
        ]
