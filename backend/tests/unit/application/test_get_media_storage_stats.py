from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.application.use_cases.get_media_storage_stats import (
    GetMediaStorageStatsUseCase,
)
from backend.domain.value_objects.source_type import SourceType


@pytest.mark.unit
class TestGetMediaStorageStats:
    def test_aggregates_sizes_per_source(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        (media_root / "1").mkdir(parents=True)
        (media_root / "2").mkdir(parents=True)

        # Source 1: 1 screenshot (100b) + 1 audio (200b)
        (media_root / "1" / "10_screenshot.webp").write_bytes(b"x" * 100)
        (media_root / "1" / "10_audio.m4a").write_bytes(b"x" * 200)
        # Source 2: 2 screenshots
        (media_root / "2" / "20_screenshot.webp").write_bytes(b"x" * 50)
        (media_root / "2" / "21_screenshot.webp").write_bytes(b"x" * 75)

        source1 = MagicMock()
        source1.id = 1
        source1.title = "Movie A"
        source1.source_type = SourceType.VIDEO
        source2 = MagicMock()
        source2.id = 2
        source2.title = "Movie B"
        source2.source_type = SourceType.VIDEO

        source_repo = MagicMock()
        source_repo.list_all.return_value = [source1, source2]

        uc = GetMediaStorageStatsUseCase(
            source_repo=source_repo,
            media_root=str(media_root),
        )

        stats = uc.execute()

        assert len(stats) == 2
        by_id = {s.source_id: s for s in stats}
        assert by_id[1].screenshot_bytes == 100
        assert by_id[1].audio_bytes == 200
        assert by_id[1].screenshot_count == 1
        assert by_id[1].audio_count == 1
        assert by_id[1].source_title == "Movie A"
        assert by_id[2].screenshot_bytes == 125
        assert by_id[2].audio_bytes == 0
        assert by_id[2].screenshot_count == 2
        assert by_id[2].audio_count == 0

    def test_skips_non_video_sources(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        media_root.mkdir()

        text_source = MagicMock()
        text_source.id = 1
        text_source.source_type = SourceType.TEXT

        source_repo = MagicMock()
        source_repo.list_all.return_value = [text_source]

        uc = GetMediaStorageStatsUseCase(
            source_repo=source_repo,
            media_root=str(media_root),
        )

        stats = uc.execute()

        assert stats == []

    def test_returns_zero_for_video_without_media_dir(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        media_root.mkdir()

        video_source = MagicMock()
        video_source.id = 7
        video_source.title = "Empty"
        video_source.source_type = SourceType.VIDEO

        source_repo = MagicMock()
        source_repo.list_all.return_value = [video_source]

        uc = GetMediaStorageStatsUseCase(
            source_repo=source_repo,
            media_root=str(media_root),
        )

        stats = uc.execute()

        assert len(stats) == 1
        assert stats[0].screenshot_bytes == 0
        assert stats[0].audio_bytes == 0
        assert stats[0].screenshot_count == 0
        assert stats[0].audio_count == 0

    def test_uses_default_title_when_source_title_is_none(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        media_root = tmp_path / "media"
        media_root.mkdir()

        video_source = MagicMock()
        video_source.id = 99
        video_source.title = None
        video_source.source_type = SourceType.VIDEO

        source_repo = MagicMock()
        source_repo.list_all.return_value = [video_source]

        uc = GetMediaStorageStatsUseCase(
            source_repo=source_repo,
            media_root=str(media_root),
        )

        stats = uc.execute()

        assert stats[0].source_title == "Source 99"
