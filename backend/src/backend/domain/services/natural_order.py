from __future__ import annotations

import re

_NUMBERS = re.compile(r"(\d+)")


def natural_key(text: str) -> tuple[tuple[int, int, str], ...]:
    """Case-insensitive, numbers by value: `ch2` before `ch10`."""
    return tuple(
        (0, int(part), "") if part.isdigit() else (1, 0, part)
        for part in _NUMBERS.split(text.casefold()) if part
    )
