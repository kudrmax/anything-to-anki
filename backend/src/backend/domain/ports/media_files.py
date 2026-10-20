from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.value_objects.media_file_draft import MediaFileDraft


class MediaFiles(ABC):
    """Port for the media files made for phrases.

    A file is made as a draft beside its final name and takes that name only when kept, so
    a result that turns out stale never replaces the phrase's current file.
    """

    @abstractmethod
    def draft(self, source_id: int, phrase_id: int, name: str) -> MediaFileDraft:
        """A new draft for the phrase's file `name` (e.g. "tts.m4a"); its folder is made."""

    @abstractmethod
    def keep(self, draft: MediaFileDraft) -> None:
        """Put the written draft in place of the final file."""

    @abstractmethod
    def discard(self, draft: MediaFileDraft) -> None:
        """Drop the draft if it is still there; a kept draft is gone already."""

    @abstractmethod
    def remove(self, paths: Sequence[str]) -> None:
        """Remove the final files of phrases that no longer have them; a missing one is
        gone already."""
