from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel


class CreateCollectionRequest(BaseModel):
    """Input for creating a new collection."""

    name: str


class RenameCollectionRequest(BaseModel):
    """Input for renaming a collection."""

    name: str


class AssignCollectionRequest(BaseModel):
    """Input for assigning a source to a collection."""

    collection_id: int | None = None


class CollectionDTO(BaseModel):
    """Summary view of a collection."""

    id: int
    name: str
    source_count: int
    created_at: datetime
