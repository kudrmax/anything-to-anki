from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.image_provider import ImageProvider


@dataclass(frozen=True)
class ImageOption:
    """A picture the user may pick for a target: where to download it and who offers it."""

    url: str
    provider: ImageProvider
