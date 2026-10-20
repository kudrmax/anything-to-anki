from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NumberFormat:
    """How `{{n}}` is written: padded with zeros to `digits`, or, without digits, to the
    count of sources, so titles sort by name in order (`01`…`11`)."""

    digits: int | None = None

    def __post_init__(self) -> None:
        if self.digits is not None and self.digits < 1:
            msg = "A number has at least 1 digit"
            raise ValueError(msg)

    def width(self, total: int) -> int:
        return max(self.digits or len(str(total)), len(str(total)))
