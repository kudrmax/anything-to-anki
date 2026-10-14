from __future__ import annotations

import unicodedata

# A letter's Unicode name starts with its script:
# "LATIN SMALL LETTER E WITH ACUTE", "CYRILLIC SMALL LETTER A".
LATIN_LETTER_NAME_PREFIX = "LATIN"


def is_english(text: str) -> bool:
    """Whether a line is written in English: it has letters, and all of them are Latin.

    A card phrase is always English, while a topic is typed in any language, so a line
    with Cyrillic or any other script is never a phrase. A line without letters isn't
    English either.
    """
    letters = [char for char in text if char.isalpha()]
    return bool(letters) and all(
        unicodedata.name(char, "").startswith(LATIN_LETTER_NAME_PREFIX) for char in letters
    )
