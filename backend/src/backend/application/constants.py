"""Shared application-layer constants."""

from __future__ import annotations

DEFAULT_USAGE_GROUP_ORDER: list[str] = [
    "neutral",
    "informal",
    "formal",
    "specialized",
    "connotation",
    "old-fashioned",
    "offensive",
    "other",
]

FREQUENT_WORD_THRESHOLD_SETTING: str = "frequent_word_threshold"
USAGE_GROUP_ORDER_SETTING: str = "usage_group_order"

# The best cards come first; the user decides on a short list, the rest waits behind "show more".
INITIALLY_SHOWN_CANDIDATES: int = 15
