from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.persistence.database import reconcile_media_files


@pytest.mark.unit
class TestReconcileMediaFiles:
    def test_removes_directory_for_missing_source(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        # Setup: media/42/ exists, but source 42 does NOT exist in DB.
        media_root = tmp_path / "media"
        (media_root / "42").mkdir(parents=True)
        (media_root / "42" / "1_screenshot.webp").write_bytes(b"x")

        session = MagicMock()
        session_factory = MagicMock(return_value=session)

        with patch("backend.infrastructure.persistence.sqla_source_repository.SqlaSourceRepository") as src_cls, \
             patch("backend.infrastructure.persistence.sqla_candidate_repository.SqlaCandidateRepository") as cand_cls:
            src_cls.return_value.get_by_id.return_value = None
            cand_cls.return_value.get_by_id.return_value = None
            reconcile_media_files(session_factory, str(media_root))

        assert not (media_root / "42").exists()

    def test_removes_orphan_file_in_valid_source_dir(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        valid_file = media_root / "1" / "10_screenshot.webp"
        orphan_file = media_root / "1" / "99_screenshot.webp"
        valid_file.write_bytes(b"keep")
        orphan_file.write_bytes(b"orphan")

        session = MagicMock()
        session_factory = MagicMock(return_value=session)

        with patch("backend.infrastructure.persistence.sqla_source_repository.SqlaSourceRepository") as src_cls, \
             patch("backend.infrastructure.persistence.sqla_candidate_repository.SqlaCandidateRepository") as cand_cls:
            # source 1 exists
            src_cls.return_value.get_by_id.return_value = MagicMock(id=1)
            # candidate 10 exists, 99 does not
            def cand_lookup(cid: int) -> MagicMock | None:
                return MagicMock(id=10) if cid == 10 else None
            cand_cls.return_value.get_by_id.side_effect = cand_lookup
            reconcile_media_files(session_factory, str(media_root))

        assert valid_file.exists()
        assert not orphan_file.exists()

    def test_ignores_non_numeric_dirs(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        (media_root / "tmp_upload").mkdir(parents=True)
        dont_touch = media_root / "tmp_upload" / "file.txt"
        dont_touch.write_bytes(b"x")

        session = MagicMock()
        session_factory = MagicMock(return_value=session)

        with patch("backend.infrastructure.persistence.sqla_source_repository.SqlaSourceRepository"), \
             patch("backend.infrastructure.persistence.sqla_candidate_repository.SqlaCandidateRepository"):
            reconcile_media_files(session_factory, str(media_root))

        assert dont_touch.exists()

    def test_ignores_unknown_files_in_valid_source_dir(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        unknown = media_root / "1" / "notes.txt"
        unknown.write_bytes(b"user's notes")

        session = MagicMock()
        session_factory = MagicMock(return_value=session)

        with patch("backend.infrastructure.persistence.sqla_source_repository.SqlaSourceRepository") as src_cls, \
             patch("backend.infrastructure.persistence.sqla_candidate_repository.SqlaCandidateRepository"):
            src_cls.return_value.get_by_id.return_value = MagicMock(id=1)
            reconcile_media_files(session_factory, str(media_root))

        assert unknown.exists()

    def test_missing_media_root_is_noop(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        session_factory = MagicMock()
        # Should not raise
        reconcile_media_files(session_factory, str(tmp_path / "nonexistent"))

    def test_proceeds_when_db_count_equals_disk_dirs(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        # Single source dir, source exists in DB → file must be preserved.
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        (media_root / "1" / "1_screenshot.webp").write_bytes(b"x")

        session = MagicMock()
        session_factory = MagicMock(return_value=session)

        with patch("backend.infrastructure.persistence.sqla_source_repository.SqlaSourceRepository") as src_cls, \
             patch("backend.infrastructure.persistence.sqla_candidate_repository.SqlaCandidateRepository") as cand_cls:
            src_cls.return_value.get_by_id.return_value = MagicMock(id=1)
            cand_cls.return_value.get_by_id.return_value = MagicMock(id=1)
            reconcile_media_files(session_factory, str(media_root))

        # File preserved (source exists)
        assert (media_root / "1" / "1_screenshot.webp").exists()
        # Repo WAS queried — reconcile iterated through the dir.
        src_cls.return_value.get_by_id.assert_called_with(1)
