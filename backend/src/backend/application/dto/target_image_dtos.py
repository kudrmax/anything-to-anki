from __future__ import annotations

from pydantic import BaseModel


class ImageOptionDTO(BaseModel):
    """A picture offered for a target."""

    url: str
    provider: str  # 'wiktionary' | 'bing'


class TargetImageOptionsDTO(BaseModel):
    """Pictures to choose from for a target, best first, with the query they were found by."""

    query: str
    options: list[ImageOptionDTO]


class ApplyTargetImageRequest(BaseModel):
    """Input for putting a picked picture on the card."""

    url: str
