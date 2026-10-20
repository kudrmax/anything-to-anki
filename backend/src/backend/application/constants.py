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

# How many pictures each picture source may offer for one target.
IMAGES_PER_SOURCE_SETTING: str = "images_per_source"
DEFAULT_IMAGES_PER_SOURCE: int = 12
MIN_IMAGES_PER_SOURCE: int = 1
MAX_IMAGES_PER_SOURCE: int = 30

# The best cards come first; the user decides on a short list, the rest waits behind "show more".
INITIALLY_SHOWN_CANDIDATES: int = 15

# Which hint a new cloze card gets until the user picks another one.
CLOZE_DEFAULT_HINT_SETTING: str = "cloze_default_hint"
DEFAULT_CLOZE_HINT: str = "none"

# How a source made from one chapter of a book is titled.
BOOK_CHAPTER_TITLE_SETTING: str = "book_chapter_title_template"

# How the sources list is grouped and sorted: one choice for every set of sources.
SOURCE_GROUPING_SETTING: str = "source_grouping"
SOURCE_SORT_SETTING: str = "source_sort"
