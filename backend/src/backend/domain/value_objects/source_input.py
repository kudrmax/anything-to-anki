from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PastedText:
    text: str


@dataclass(frozen=True)
class LocalFile:
    path: str
    subtitles_path: str | None = None


@dataclass(frozen=True)
class Url:
    url: str


type SourceInput = PastedText | LocalFile | Url
