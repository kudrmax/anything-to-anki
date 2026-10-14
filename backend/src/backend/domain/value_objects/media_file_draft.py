from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaFileDraft:
    """A media file being made: written at `path`, it takes `final_path` only when kept."""

    path: str
    final_path: str
