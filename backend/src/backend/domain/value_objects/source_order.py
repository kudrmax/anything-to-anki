from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SourceGrouping(StrEnum):
    """How the sources list is split: by stage, or one list."""

    STAGE = "stage"
    NONE = "none"


class SourceSort(StrEnum):
    """How sources follow each other inside a group."""

    ADDED = "added"
    NAME = "name"
    LAST_STUDIED = "last_studied"


DEFAULT_SOURCE_GROUPING = SourceGrouping.STAGE
DEFAULT_SOURCE_SORT = SourceSort.ADDED


@dataclass(frozen=True)
class SourceOrder:
    """The user's one choice of how sources follow each other, everywhere in the app."""

    grouping: SourceGrouping = DEFAULT_SOURCE_GROUPING
    sort: SourceSort = DEFAULT_SOURCE_SORT
