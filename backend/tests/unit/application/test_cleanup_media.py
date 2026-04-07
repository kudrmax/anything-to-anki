from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.application.dto.media_dtos import CleanupMediaKind
from backend.application.use_cases.cleanup_media import CleanupMediaUseCase
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.value_objects.enrichment_status import EnrichmentStatus


def _make_candidate(cid: int, screenshot_path: str | None, audio_path: str | None) -> MagicMock:
    c = MagicMock()
    c.id = cid
    c.media = CandidateMedia(
        candidate_id=cid,
        screenshot_path=screenshot_path,
        audio_path=audio_path,
        start_ms=1000,
        end_ms=2000,
        status=EnrichmentStatus.DONE,
        error=None,
        generated_at=None,
    )
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
        media_repo = MagicMock()

        uc = CleanupMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=media_repo,
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.ALL)

        assert not shot.exists()
        assert not audio.exists()
        media_repo.clear_paths.assert_called_once_with(
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
        media_repo = MagicMock()

        uc = CleanupMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=media_repo,
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.IMAGES)

        assert not shot.exists()
        assert audio.exists()
        media_repo.clear_paths.assert_called_once_with(
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
        media_repo = MagicMock()

        uc = CleanupMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=media_repo,
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.AUDIO)

        assert shot.exists()
        assert not audio.exists()
        media_repo.clear_paths.assert_called_once_with(
            10, clear_screenshot=False, clear_audio=True
        )

    def test_missing_file_on_disk_still_clears_db(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        source_dir = media_root / "1"
        source_dir.mkdir(parents=True)

        candidate = _make_candidate(10, "/nonexistent/path.webp", "/nonexistent/path.m4a")
        candidate_repo = MagicMock()
        candidate_repo.get_by_source.return_value = [candidate]
        media_repo = MagicMock()

        uc = CleanupMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=media_repo,
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.ALL)

        media_repo.clear_paths.assert_called_once()

    def test_candidate_without_media_skipped(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        source_dir = media_root / "1"
        source_dir.mkdir(parents=True)

        # Candidate with no media row at all (media=None)
        candidate = MagicMock()
        candidate.id = 10
        candidate.media = None

        candidate_repo = MagicMock()
        candidate_repo.get_by_source.return_value = [candidate]
        media_repo = MagicMock()

        uc = CleanupMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=media_repo,
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.ALL)

        # No DB call since candidate has no media row
        media_repo.clear_paths.assert_not_called()
