from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.collection_repository import CollectionRepository
from backend.infrastructure.persistence.models import CollectionModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.collection import Collection


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

    def list_all(self) -> list[Collection]:
        models = (
            self._session.query(CollectionModel)
            .order_by(CollectionModel.name)
            .all()
        )
        return [m.to_entity() for m in models]

    def rename(self, collection_id: int, new_name: str) -> Collection:
        model = self._session.get(CollectionModel, collection_id)
        if model is None:
            from backend.domain.exceptions import CollectionNotFoundError
            raise CollectionNotFoundError(collection_id)
        model.name = new_name
        self._session.flush()
        return model.to_entity()

    def delete(self, collection_id: int) -> None:
        model = self._session.get(CollectionModel, collection_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
