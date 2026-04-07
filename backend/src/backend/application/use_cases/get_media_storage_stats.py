from __future__ import annotations

import os
from typing import TYPE_CHECKING

from backend.application.dto.media_dtos import SourceMediaStats
from backend.domain.value_objects.source_type import SourceType

if TYPE_CHECKING:
    from backend.domain.ports.source_repository import SourceRepository


class GetMediaStorageStatsUseCase:
    """Aggregates on-disk media footprint for each video source."""

    def __init__(
        self,
        source_repo: SourceRepository,
        media_root: str,
    ) -> None:
        self._source_repo = source_repo
        self._media_root = media_root

    def execute(self) -> list[SourceMediaStats]:
        stats: list[SourceMediaStats] = []
        for source in self._source_repo.list_all():
            if source.source_type != SourceType.VIDEO:
                continue

            source_dir = os.path.join(self._media_root, str(source.id))
            screenshot_bytes = 0
            audio_bytes = 0
            screenshot_count = 0
            audio_count = 0

            if os.path.isdir(source_dir):
                for fname in os.listdir(source_dir):
                    fpath = os.path.join(source_dir, fname)
                    if not os.path.isfile(fpath):
                        continue
                    size = os.path.getsize(fpath)
                    if "_screenshot." in fname:
                        screenshot_bytes += size
                        screenshot_count += 1
                    elif "_audio." in fname:
                        audio_bytes += size
                        audio_count += 1

            stats.append(SourceMediaStats(
                source_id=source.id,
                source_title=source.title or f"Source {source.id}",
                screenshot_bytes=screenshot_bytes,
                audio_bytes=audio_bytes,
                screenshot_count=screenshot_count,
                audio_count=audio_count,
            ))
        return stats
