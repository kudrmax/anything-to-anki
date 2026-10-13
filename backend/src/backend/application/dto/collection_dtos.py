from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from backend.domain.entities.collection import Collection


class CreateCollectionRequest(BaseModel):
    name: str
    parent_id: int | None = None


class RenameCollectionRequest(BaseModel):
    name: str


class MoveCollectionRequest(BaseModel):
    """`position` is the index among the new siblings, not counting the moved collection."""

    parent_id: int | None = None
    position: int


class CollectionDTO(BaseModel):
    id: int
    name: str
    parent_id: int | None
    position: int


class RenamedCollectionDTO(BaseModel):
    id: int
    name: str
    previous_name: str


class MovedCollectionDTO(BaseModel):
    id: int
    previous_parent_id: int | None
    previous_position: int


class DeletedCollectionDTO(BaseModel):
    id: int
    name: str
    evicted_source_count: int


class ScopeCountsDTO(BaseModel):
    total: int
    reviewed: int
    pending: int


class CollectionNodeDTO(BaseModel):
    id: int
    name: str
    parent_id: int | None
    counts: ScopeCountsDTO
    # Drag & drop hints: may hold subcollections; may itself become a subcollection.
    accepts_collections: bool
    can_be_nested: bool
    children: list[CollectionNodeDTO]


class CollectionTreeDTO(BaseModel):
    all: ScopeCountsDTO
    unsorted: ScopeCountsDTO
    collections: list[CollectionNodeDTO]


class SourcePlacementDTO(BaseModel):
    source_id: int
    collection_id: int | None


class PlaceSourcesRequest(BaseModel):
    placements: list[SourcePlacementDTO]


class PlacedSourcesDTO(BaseModel):
    previous: list[SourcePlacementDTO]


class SourceIdsRequest(BaseModel):
    source_ids: list[int]


class StartedSourcesDTO(BaseModel):
    started: list[int]


class DeletedSourcesDTO(BaseModel):
    deleted: list[int]
    skipped: list[int]


def collection_to_dto(collection: Collection) -> CollectionDTO:
    assert collection.id is not None
    return CollectionDTO(
        id=collection.id,
        name=collection.name,
        parent_id=collection.parent_id,
        position=collection.position,
    )
