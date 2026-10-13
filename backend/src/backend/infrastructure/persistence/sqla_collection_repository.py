from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import CollectionNotFoundError
from backend.domain.ports.collection_repository import CollectionRepository
from backend.infrastructure.persistence.models import CollectionEvictionModel, CollectionModel

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.orm import Session

    from backend.domain.entities.collection import Collection
    from backend.domain.value_objects.source_eviction import SourceEviction


class SqlaCollectionRepository(CollectionRepository):
    """SQLAlchemy implementation of CollectionRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, collection: Collection) -> Collection:
        model = CollectionModel.from_entity(collection)
        self._session.add(model)
        self._session.flush()
        return model.to_entity()

    def get_by_id(self, collection_id: int) -> Collection | None:
        model = self._session.get(CollectionModel, collection_id)
        return model.to_entity() if model else None

    def list_all(self, *, include_deleted: bool = False) -> list[Collection]:
        query = self._session.query(CollectionModel)
        if not include_deleted:
            query = query.filter(CollectionModel.deleted_at.is_(None))
        models = query.order_by(CollectionModel.position, CollectionModel.id)
        return [m.to_entity() for m in models]

    def save(self, collections: Sequence[Collection]) -> None:
        for collection in collections:
            assert collection.id is not None
            model = self._session.get(CollectionModel, collection.id)
            if model is None:
                raise CollectionNotFoundError(collection.id)
            model.name = collection.name
            model.parent_id = collection.parent_id
            model.position = collection.position
            model.deleted_at = collection.deleted_at
        self._session.flush()

    def record_evictions(
        self, collection_id: int, evictions: Sequence[SourceEviction],
    ) -> None:
        self._session.add_all(
            CollectionEvictionModel(
                collection_id=collection_id,
                source_id=e.source_id,
                previous_collection_id=e.previous_collection_id,
                moved_to_collection_id=e.moved_to_collection_id,
            )
            for e in evictions
        )
        self._session.flush()

    def take_evictions(self, collection_id: int) -> list[SourceEviction]:
        models = (
            self._session.query(CollectionEvictionModel)
            .filter(CollectionEvictionModel.collection_id == collection_id)
            .order_by(CollectionEvictionModel.id)
            .all()
        )
        evictions = [m.to_value() for m in models]
        for model in models:
            self._session.delete(model)
        self._session.flush()
        return evictions

    def rename(self, collection_id: int, new_name: str) -> Collection:
        model = self._session.get(CollectionModel, collection_id)
        if model is None:
            raise CollectionNotFoundError(collection_id)
        model.name = new_name
        self._session.flush()
        return model.to_entity()

    def delete(self, collection_id: int) -> None:
        model = self._session.get(CollectionModel, collection_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
