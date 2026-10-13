from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.document import Document


class Kind(StrEnum):
    """What the content is for the product, regardless of the file it came from."""

    TEXT = "text"
    BOOK = "book"
    SUBTITLES = "subtitles"
    SONG = "song"


@dataclass(frozen=True)
class LocalVideo:
    path: str
    audio_track: int | None = None


@dataclass(frozen=True)
class YouTubeVideo:
    """A video that is downloaded later, on the user's request."""

    url: str


type VideoRef = LocalVideo | YouTubeVideo


@dataclass(frozen=True)
class TextContent:
    title: str | None
    document: Document

    @property
    def kind(self) -> Kind:
        return Kind.TEXT


@dataclass(frozen=True)
class Chapter:
    title: str | None
    document: Document


@dataclass(frozen=True)
class BookContent:
    title: str | None
    chapters: tuple[Chapter, ...]

    @property
    def kind(self) -> Kind:
        return Kind.BOOK


@dataclass(frozen=True)
class SubtitlesContent:
    title: str | None
    document: Document
    video: VideoRef | None = None

    @property
    def kind(self) -> Kind:
        return Kind.SUBTITLES


@dataclass(frozen=True)
class SongContent:
    title: str | None
    document: Document

    @property
    def kind(self) -> Kind:
        return Kind.SONG


type Content = TextContent | BookContent | SubtitlesContent | SongContent
