from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from backend.application.dto.source_dtos import ProgressDTO
from backend.domain.value_objects.source_operation_kind import SourceOperationKind  # noqa: TC001

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
    position: int = Field(ge=0)


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
    # The progress of all the scope's sources summed, as each source shows it.
    progress: ProgressDTO
    # The scope read as one set under review, as a source reads: its status ('processing'
    # while it is processed), whether there is something to process, whether it opens for
    # review, how far the review got (0..1) and the line under the progress.
    status: str
    can_process: bool
    can_review: bool
    review_fraction: float
    progress_caption: str
    # How the set is brought up to date and whether it can be exported, as a source tells.
    available_operations: list[SourceOperationKind] = []
    can_start_operation: bool = True
    operation_hint: str | None = None
    can_export: bool = False


class CollectionNodeDTO(BaseModel):
    id: int
    name: str
    parent_id: int | None
    counts: ScopeCountsDTO
    depth: int
    # May hold subcollections; the parents it may move under, None being the top level.
    accepts_collections: bool
    move_targets: list[int | None]
    children: list[CollectionNodeDTO]


class CollectionTreeDTO(BaseModel):
    all: ScopeCountsDTO
    unsorted: ScopeCountsDTO
    max_depth: int
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
    skipped: list[int]


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
