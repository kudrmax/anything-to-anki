from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call

import pytest
from backend.application.use_cases.delete_source import DeleteSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.exceptions import SourceIsProcessingError, SourceNotFoundError
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
class TestDeleteSourceUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.candidate_repo = MagicMock()
        self.use_case = DeleteSourceUseCase(
            source_repo=self.source_repo,
            candidate_repo=self.candidate_repo,
            media_root="/tmp/nonexistent-media-root",
        )

    def test_deletes_candidates_then_source(self) -> None:
        self.source_repo.get_by_id.return_value = Source(
            id=1, raw_text="Hello", status=SourceStatus.DONE
        )
        manager = MagicMock()
        manager.attach_mock(self.candidate_repo.delete_by_source, "delete_by_source")
        manager.attach_mock(self.source_repo.delete, "delete")

        self.use_case.execute(1)

        assert manager.mock_calls == [
            call.delete_by_source(1),
            call.delete(1),
        ]

    def test_not_found_raises(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.execute(999)
        self.candidate_repo.delete_by_source.assert_not_called()
        self.source_repo.delete.assert_not_called()

    def test_processing_raises(self) -> None:
        self.source_repo.get_by_id.return_value = Source(
            id=1, raw_text="Hello", status=SourceStatus.PROCESSING
        )
        with pytest.raises(SourceIsProcessingError):
            self.use_case.execute(1)
        self.candidate_repo.delete_by_source.assert_not_called()
        self.source_repo.delete.assert_not_called()

    def test_deletes_media_directory_when_present(self, tmp_path: Path) -> None:
        # Simulate a media directory with files
        media_root = tmp_path / "media"
        source_media = media_root / "42"
        source_media.mkdir(parents=True)
        (source_media / "1_screenshot.webp").write_bytes(b"fake image")
        (source_media / "1_audio.m4a").write_bytes(b"fake audio")
        assert source_media.exists()

        source_repo = MagicMock()
        candidate_repo = MagicMock()
        source_repo.get_by_id.return_value = Source(
            id=42, raw_text="video srt", status=SourceStatus.DONE
        )
        uc = DeleteSourceUseCase(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            media_root=str(media_root),
        )

        uc.execute(42)

        assert not source_media.exists()
        candidate_repo.delete_by_source.assert_called_once_with(42)
        source_repo.delete.assert_called_once_with(42)

    def test_delete_does_not_fail_if_media_dir_missing(self, tmp_path: Path) -> None:
        media_root = tmp_path / "media"
        media_root.mkdir()

        source_repo = MagicMock()
        candidate_repo = MagicMock()
        source_repo.get_by_id.return_value = Source(
            id=42, raw_text="text", status=SourceStatus.DONE
        )
        uc = DeleteSourceUseCase(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            media_root=str(media_root),
        )

        # Should not raise
        uc.execute(42)

        source_repo.delete.assert_called_once_with(42)
