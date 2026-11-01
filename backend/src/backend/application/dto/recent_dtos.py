from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from backend.application.dto.collection_dtos import CollectionNodeDTO  # noqa: TC001
from backend.application.dto.source_dtos import SourceDTO  # noqa: TC001


class RecentSourceDTO(BaseModel):
    kind: Literal["source"] = "source"
    used_at: datetime
    source: SourceDTO


class RecentCollectionDTO(BaseModel):
    kind: Literal["collection"] = "collection"
    used_at: datetime
    collection: CollectionNodeDTO
    # The names of the collections above it, from the top.
    path: list[str]


class RecentBoardDTO(BaseModel):
    """The sources and collections the user worked with, the latest first."""

    items: list[Annotated[RecentSourceDTO | RecentCollectionDTO, Field(discriminator="kind")]]
