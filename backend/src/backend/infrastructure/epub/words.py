from __future__ import annotations

import re

_WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")


def count_words(text: str) -> int:
    return sum(1 for _ in _WORD_RE.finditer(text))
