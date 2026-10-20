"""Media files for tests that only need to know which files a rebuild removed."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.media_files import MediaFiles
from backend.domain.value_objects.fragment_selection_config import ScoringConfig

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.value_objects.media_file_draft import MediaFileDraft

WEIGHT_UNKNOWN = ScoringConfig().weight_unknown


class RemovedMediaFiles(MediaFiles):
    """Makes no files; `removed` lists every path asked to go, in order."""

    def __init__(self) -> None:
        self.removed: list[str] = []

    def draft(self, source_id: int, phrase_id: int, name: str) -> MediaFileDraft:
        raise NotImplementedError

    def keep(self, draft: MediaFileDraft) -> None:
        raise NotImplementedError

    def discard(self, draft: MediaFileDraft) -> None:
        raise NotImplementedError

    def remove(self, paths: Sequence[str]) -> None:
        self.removed.extend(paths)
