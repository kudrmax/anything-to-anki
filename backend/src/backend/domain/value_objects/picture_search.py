from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.image_option import ImageOption


class PictureSearchStatus(StrEnum):
    SEARCHING = "searching"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True)
class PictureSearch:
    """How a picture search run apart from requests stands: still going, done with its
    pictures (best first), or failed."""

    status: PictureSearchStatus
    options: tuple[ImageOption, ...] = field(default=())
