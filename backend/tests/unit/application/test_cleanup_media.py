from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.application.dto.media_dtos import CleanupMediaKind
from backend.application.use_cases.cleanup_media import CleanupMediaUseCase


def _make_candidate(cid: int, screenshot_path: str | None, audio_path: str | None) -> MagicMock:
    c = MagicMock()
    c.id = cid
    c.screenshot_path = screenshot_path
    c.audio_path = audio_path
    return c


@pytest.mark.unit
class TestCleanupMedia:
    def test_all_removes_files_and_clears_db(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        source_dir = media_root / "1"
        source_dir.mkdir(parents=True)
        shot = source_dir / "10_screenshot.webp"
        audio = source_dir / "10_audio.m4a"
        shot.write_bytes(b"x")
        audio.write_bytes(b"y")

        candidate = _make_candidate(10, str(shot), str(audio))
        candidate_repo = MagicMock()
        candidate_repo.get_by_source.return_value = [candidate]

        uc = CleanupMediaUseCase(
            candidate_repo=candidate_repo,
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.ALL)

        assert not shot.exists()
        assert not audio.exists()
        candidate_repo.clear_media_path.assert_called_once_with(
            10, clear_screenshot=True, clear_audio=True
        )
        # Empty source dir is removed
        assert not source_dir.exists()

    def test_images_only_leaves_audio(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        source_dir = media_root / "1"
        source_dir.mkdir(parents=True)
        shot = source_dir / "10_screenshot.webp"
        audio = source_dir / "10_audio.m4a"
        shot.write_bytes(b"x")
        audio.write_bytes(b"y")

        candidate = _make_candidate(10, str(shot), str(audio))
        candidate_repo = MagicMock()
        candidate_repo.get_by_source.return_value = [candidate]

        uc = CleanupMediaUseCase(
            candidate_repo=candidate_repo,
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.IMAGES)

        assert not shot.exists()
        assert audio.exists()
        candidate_repo.clear_media_path.assert_called_once_with(
            10, clear_screenshot=True, clear_audio=False
        )
        assert source_dir.exists()  # non-empty

    def test_audio_only_leaves_screenshots(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        source_dir = media_root / "1"
        source_dir.mkdir(parents=True)
        shot = source_dir / "10_screenshot.webp"
        audio = source_dir / "10_audio.m4a"
        shot.write_bytes(b"x")
        audio.write_bytes(b"y")

        candidate = _make_candidate(10, str(shot), str(audio))
        candidate_repo = MagicMock()
        candidate_repo.get_by_source.return_value = [candidate]

        uc = CleanupMediaUseCase(
            candidate_repo=candidate_repo,
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.AUDIO)

        assert shot.exists()
        assert not audio.exists()
        candidate_repo.clear_media_path.assert_called_once_with(
            10, clear_screenshot=False, clear_audio=True
        )

    def test_missing_file_on_disk_still_clears_db(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        source_dir = media_root / "1"
        source_dir.mkdir(parents=True)

        candidate = _make_candidate(10, "/nonexistent/path.webp", "/nonexistent/path.m4a")
        candidate_repo = MagicMock()
        candidate_repo.get_by_source.return_value = [candidate]

        uc = CleanupMediaUseCase(
            candidate_repo=candidate_repo,
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.ALL)

        candidate_repo.clear_media_path.assert_called_once()

    def test_candidate_without_paths_still_gets_db_cleared(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        source_dir = media_root / "1"
        source_dir.mkdir(parents=True)

        candidate = _make_candidate(10, None, None)
        candidate_repo = MagicMock()
        candidate_repo.get_by_source.return_value = [candidate]

        uc = CleanupMediaUseCase(
            candidate_repo=candidate_repo,
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.ALL)

        # Called to be safe — even if paths were None, DB should be normalized
        candidate_repo.clear_media_path.assert_called_once()
