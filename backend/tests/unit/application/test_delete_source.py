from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call

import pytest
from backend.application.use_cases.delete_source import DeleteSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.exceptions import (
    PermanentSourceError,
    SourceIsProcessingError,
    SourceNotFoundError,
)
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from pathlib import Path


def _free_lock() -> MagicMock:
    lock = MagicMock()
    lock.held.return_value = None
    return lock


@pytest.mark.unit
class TestDeleteSourceUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.candidate_repo = MagicMock()
        self.lock = _free_lock()
        self.use_case = DeleteSourceUseCase(
            source_repo=self.source_repo,
            candidate_repo=self.candidate_repo,
            lock=self.lock,
            media_root="/tmp/nonexistent-media-root",
        )

    def test_deletes_candidates_then_source(self) -> None:
        self.source_repo.get_by_id.return_value = Source(
            id=1, status=SourceStatus.DONE, format=Format.PLAIN, kind=Kind.TEXT,
            )
        manager = MagicMock()
        manager.attach_mock(self.candidate_repo.delete_by_source, "delete_by_source")
        manager.attach_mock(self.source_repo.delete, "delete")

        self.use_case.execute(1)

        assert manager.mock_calls == [
            call.delete_by_source(1),
            call.delete(1),
        ]

    def test_saved_phrases_source_is_not_deleted(self) -> None:
        saved_source = Source.saved_phrases()
        saved_source.id = 1
        self.source_repo.get_by_id.return_value = saved_source

        with pytest.raises(PermanentSourceError):
            self.use_case.execute(1)

        self.source_repo.delete.assert_not_called()

    def test_not_found_raises(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.execute(999)
        self.candidate_repo.delete_by_source.assert_not_called()
        self.source_repo.delete.assert_not_called()

    def test_a_source_held_by_an_operation_is_not_deleted(self) -> None:
        self.source_repo.get_by_id.return_value = Source(
            id=1, status=SourceStatus.DONE, format=Format.PLAIN, kind=Kind.TEXT,
            )
        self.lock.held.return_value = SourceOperationKind.REBUILD
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
            id=42, status=SourceStatus.DONE, format=Format.PLAIN, kind=Kind.TEXT,
            )
        uc = DeleteSourceUseCase(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            lock=_free_lock(),
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
            id=42, status=SourceStatus.DONE, format=Format.PLAIN, kind=Kind.TEXT,
            )
        uc = DeleteSourceUseCase(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            lock=_free_lock(),
            media_root=str(media_root),
        )

        # Should not raise
        uc.execute(42)

        source_repo.delete.assert_called_once_with(42)
