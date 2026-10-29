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

CEFR_LEVEL_SETTING: str = "cefr_level"
DEFAULT_CEFR_LEVEL: str = "B2"
FREQUENT_WORD_THRESHOLD_SETTING: str = "frequent_word_threshold"
USAGE_GROUP_ORDER_SETTING: str = "usage_group_order"

# How many pictures each picture source may offer for one target.
IMAGES_PER_SOURCE_SETTING: str = "images_per_source"
DEFAULT_IMAGES_PER_SOURCE: int = 12
MIN_IMAGES_PER_SOURCE: int = 1
MAX_IMAGES_PER_SOURCE: int = 30

# The most jobs a generation run queues in one write transaction: a book's run (120k
# cards) holds the writer for one chunk at a time, so a press waits well under 2 s.
GENERATION_RUN_CHUNK: int = 5_000

# How many cards a run of the next missing ones takes.
GENERATION_BATCH_SIZE_SETTING: str = "generation_batch_size"
DEFAULT_GENERATION_BATCH_SIZE: int = 100
MIN_GENERATION_BATCH_SIZE: int = 1

# An open review sends this many rows on each side of the card it lands on.
REVIEW_WINDOW_AROUND: int = 30
# The most rows one request on an open review gets.
REVIEW_ROWS_MAX: int = 200
# The most chunks of text a review opened again takes from its client: a client that read
# a whole book of 14 million characters holds about 750 chunks of TEXT_CHUNK_CHARS.
TEXT_CHUNKS_HELD_MAX: int = 2000

# Which hint a new cloze card gets until the user picks another one.
CLOZE_DEFAULT_HINT_SETTING: str = "cloze_default_hint"
DEFAULT_CLOZE_HINT: str = "none"

# How a source made from one chapter of a book is titled.
NAMING_RULE_SETTING: str = "naming_rule"

# How the sources list is grouped and sorted: one choice for every set of sources.
SOURCE_GROUPING_SETTING: str = "source_grouping"
SOURCE_SORT_SETTING: str = "source_sort"
SOURCE_SORT_DIRECTION_SETTING: str = "source_sort_direction"
