from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentPosition:
    """A piece of one block of a document: from a character of one line to one of another.

    Characters are counted in code points; the end is exclusive. A heading is line 0.
    """

    block: int
    start_line: int
    start_char: int
    end_line: int
    end_char: int

    def __post_init__(self) -> None:
        if (self.end_line, self.end_char) < (self.start_line, self.start_char):
            msg = f"A position ends before it starts: {self}"
            raise ValueError(msg)
