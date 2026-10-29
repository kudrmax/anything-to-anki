from __future__ import annotations

import re

_INNER_SEPARATORS = re.compile(r"['-]")


def is_plain_word(lemma: str) -> bool:
    """`lemma` is made of letters, with apostrophes or hyphens only between them: `o'clock`,
    `well-known`. Dictionary entries such as `10th`, `mp3`, `e.g.` or `expect'` are not."""
    return all(part.isalpha() for part in _INNER_SEPARATORS.split(lemma))
