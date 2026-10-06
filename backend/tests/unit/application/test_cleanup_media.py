from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.media_dtos import CleanupMediaKind
from backend.application.use_cases.cleanup_media import CleanupMediaUseCase
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.domain.entities.candidate_media import CandidateMedia

if TYPE_CHECKING:
    from pathlib import Path


def _make_candidate(cid: int, screenshot_path: str | None, audio_path: str | None) -> MagicMock:
    c = MagicMock()
    c.id = cid
    c.media = CandidateMedia(
        candidate_id=cid,
        screenshot_path=screenshot_path,
        audio_path=audio_path,
        start_ms=1000,
        end_ms=2000,
        generated_at=None,
    )
    c.meaning_image = None
    return c


@pytest.mark.unit
class TestCleanupMedia:
    def test_all_removes_files_and_clears_db(self, tmp_path: Path) -> None:
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
            image_repo=MagicMock(),
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

    def test_images_only_leaves_audio(self, tmp_path: Path) -> None:
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
            image_repo=MagicMock(),
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.IMAGES)

        assert not shot.exists()
        assert audio.exists()
        media_repo.clear_paths.assert_called_once_with(
            10, clear_screenshot=True, clear_audio=False
        )
        assert source_dir.exists()  # non-empty

    def test_audio_only_leaves_screenshots(self, tmp_path: Path) -> None:
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
            image_repo=MagicMock(),
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.AUDIO)

        assert shot.exists()
        assert not audio.exists()
        media_repo.clear_paths.assert_called_once_with(
            10, clear_screenshot=False, clear_audio=True
        )

    def test_missing_file_on_disk_still_clears_db(self, tmp_path: Path) -> None:
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
            image_repo=MagicMock(),
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.ALL)

        media_repo.clear_paths.assert_called_once()

    def test_candidate_without_media_skipped(self, tmp_path: Path) -> None:
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
            image_repo=MagicMock(),
            media_root=str(media_root),
        )
        uc.execute(source_id=1, kind=CleanupMediaKind.ALL)

        # No DB call since candidate has no media row
        media_repo.clear_paths.assert_not_called()


@pytest.mark.unit
class TestCleanupMeaningImages:
    def _use_case(
        self, media_root: Path, candidate: MagicMock, image_repo: MagicMock,
    ) -> CleanupMediaUseCase:
        candidate_repo = MagicMock()
        candidate_repo.get_by_source.return_value = [candidate]
        return CleanupMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=MagicMock(),
            image_repo=image_repo,
            media_root=str(media_root),
        )

    def test_images_removes_the_meaning_image_too(self, tmp_path: Path) -> None:
        picture = tmp_path / "10_meaning.abc.webp"
        picture.write_bytes(b"x")
        candidate = _make_candidate(10, None, None)
        candidate.meaning_image = CandidateMeaningImage(candidate_id=10, image_path=str(picture))
        image_repo = MagicMock()

        self._use_case(tmp_path, candidate, image_repo).execute(1, CleanupMediaKind.IMAGES)

        assert not picture.exists()
        image_repo.delete_by_candidate_id.assert_called_once_with(10)

    def test_audio_leaves_the_meaning_image(self, tmp_path: Path) -> None:
        picture = tmp_path / "10_meaning.abc.webp"
        picture.write_bytes(b"x")
        candidate = _make_candidate(10, None, None)
        candidate.meaning_image = CandidateMeaningImage(candidate_id=10, image_path=str(picture))
        image_repo = MagicMock()

        self._use_case(tmp_path, candidate, image_repo).execute(1, CleanupMediaKind.AUDIO)

        assert picture.exists()
        image_repo.delete_by_candidate_id.assert_not_called()
