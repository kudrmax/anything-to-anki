from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.entities.candidate_media import CandidateMedia


class CandidateMediaRepository(ABC):
    """Port for the media (screenshot, clip, timecodes) of phrases. No row: extraction was
    never attempted."""

    @abstractmethod
    def get_by_phrase_id(self, phrase_id: int) -> CandidateMedia | None: ...

    @abstractmethod
    def get_by_phrase_ids(self, phrase_ids: list[int]) -> dict[int, CandidateMedia]:
        """Keyed by phrase id; phrases without a row are left out."""

    @abstractmethod
    def upsert_for_phrase(self, phrase_id: int, media: CandidateMedia) -> None: ...

    @abstractmethod
    def clear_phrase_paths(
        self, phrase_id: int, *, clear_screenshot: bool, clear_audio: bool,
    ) -> None:
        """The phrase's screenshot and/or clip paths become NULL; its timecodes stay, so the
        files can be cut again."""

    @abstractmethod
    def clear_missing_file(self, path: str) -> None:
        """Every row pointing at the file — as its screenshot or its clip — loses that path;
        the rows themselves and their timecodes stay."""

    @abstractmethod
    def set_timecodes(self, times: Mapping[int, tuple[int, int] | None]) -> None:
        """Phrase id → the time of its phrase in the video, None when untimed.

        A phrase whose screenshot or clip is made keeps its media as it is: the files were
        cut at those times. No row is made for an untimed phrase."""

    @abstractmethod
    def get_all_by_source_id(self, source_id: int) -> list[CandidateMedia]:
        """The media of every phrase of the source: all its files."""
