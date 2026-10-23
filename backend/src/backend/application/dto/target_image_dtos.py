from __future__ import annotations

from pydantic import BaseModel

from backend.domain.value_objects.picture_search import (
    PictureSearchStatus,  # noqa: TC001 — Pydantic
)


class ImageOptionDTO(BaseModel):
    """A picture offered for a target."""

    url: str
    provider: str  # 'wiktionary' | 'bing' | 'yandex'


class TargetImageOptionsDTO(BaseModel):
    """Pictures to choose from for a target, best first, with the query they were found by."""

    query: str
    options: list[ImageOptionDTO]


class TargetImageSuggestionsDTO(BaseModel):
    """Pictures suggested for a target, as far as their background search has come:
    `searching` — ask again later; `ready` — `options`, best first; `failed` — none."""

    status: PictureSearchStatus
    query: str
    options: list[ImageOptionDTO]


class ApplyTargetImageRequest(BaseModel):
    """Input for putting a picked picture on the card."""

    url: str
