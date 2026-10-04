from __future__ import annotations

import string

WORD_EDGE_PUNCTUATION = string.punctuation + "“”‘’«»…—–"


def normalize_target(target: str) -> str:
    """The target as picked from the phrase's words, without punctuation stuck to them."""
    words = (word.strip(WORD_EDGE_PUNCTUATION) for word in target.split())
    return " ".join(word for word in words if word)


def phrase_contains_target(phrase: str, target: str) -> bool:
    """Every word of the target is a word of the phrase.

    Words may be apart: a separated phrasal verb ("give it up") is picked as "give up".
    """
    phrase_words = {
        word.strip(WORD_EDGE_PUNCTUATION).lower() for word in phrase.split()
    }
    target_words = normalize_target(target).lower().split()
    return bool(target_words) and all(word in phrase_words for word in target_words)
