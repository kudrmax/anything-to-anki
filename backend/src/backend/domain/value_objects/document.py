from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

MIN_HEADING_LEVEL = 1
MAX_HEADING_LEVEL = 6


class ParagraphMode(StrEnum):
    """How the lines of a paragraph relate to sentences.

    FLOW: a sentence runs on from line to line (prose, subtitles).
    LINES: every line stands on its own (songs, verse).
    """

    FLOW = "flow"
    LINES = "lines"


@dataclass(frozen=True)
class Line:
    """One line of a block: a prose paragraph, a song line or a subtitle cue."""

    text: str
    start_ms: int | None = None
    end_ms: int | None = None

    def __post_init__(self) -> None:
        if (self.start_ms is None) != (self.end_ms is None):
            msg = "A line has both start and end time or neither"
            raise ValueError(msg)
        if self.start_ms is not None and self.end_ms is not None and self.end_ms < self.start_ms:
            msg = f"A line ends before it starts: {self.start_ms}..{self.end_ms}"
            raise ValueError(msg)


@dataclass(frozen=True)
class Heading:
    level: int
    text: str

    def __post_init__(self) -> None:
        if not MIN_HEADING_LEVEL <= self.level <= MAX_HEADING_LEVEL:
            msg = f"Heading level must be {MIN_HEADING_LEVEL}..{MAX_HEADING_LEVEL}: {self.level}"
            raise ValueError(msg)


@dataclass(frozen=True)
class Paragraph:
    lines: tuple[Line, ...]
    mode: ParagraphMode


@dataclass(frozen=True)
class ListItem:
    lines: tuple[Line, ...]
    ordered: bool
    depth: int

    def __post_init__(self) -> None:
        if self.depth < 0:
            msg = f"List item depth must not be negative: {self.depth}"
            raise ValueError(msg)


type Block = Heading | Paragraph | ListItem


@dataclass(frozen=True)
class Document:
    """The text of a source as the application works with it, in reading order."""

    blocks: tuple[Block, ...]
