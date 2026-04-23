"""Map Penn Treebank POS tags to unified dictionary POS names."""
from __future__ import annotations

_PTB_TO_UNIFIED: dict[str, str] = {
    "NN": "noun", "NNS": "noun", "NNP": "noun", "NNPS": "noun",
    "VB": "verb", "VBD": "verb", "VBG": "verb", "VBN": "verb",
    "VBP": "verb", "VBZ": "verb",
    "JJ": "adjective", "JJR": "adjective", "JJS": "adjective",
    "RB": "adverb", "RBR": "adverb", "RBS": "adverb",
    "UH": "exclamation", "MD": "modal verb",
    "IN": "preposition", "DT": "determiner",
    "PRP": "pronoun", "PRP$": "pronoun", "CC": "conjunction",
}


def map_pos_tag(ptb_tag: str) -> str | None:
    """Convert a Penn Treebank POS tag to unified dictionary POS.

    Returns None if the tag is not recognized.
    """
    return _PTB_TO_UNIFIED.get(ptb_tag)
