from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.domain.ports.source_repository import SourceRepository
from backend.domain.value_objects.card_change import SourceDeleted
from backend.infrastructure.persistence.models import SourceModel, StoredCandidateModel

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy.orm import Session

    from backend.domain.entities.source import Source
    from backend.domain.ports.change_recorder import ChangeRecorder
    from backend.domain.value_objects.source_role import SourceRole
    from backend.domain.value_objects.source_status import SourceStatus


class SqlaSourceRepository(SourceRepository):
    """SQLAlchemy implementation of SourceRepository."""

    def __init__(self, session: Session, recorder: ChangeRecorder) -> None:
        self._session = session
        self._recorder = recorder

    def create(self, source: Source) -> Source:
        model = SourceModel.from_entity(source)
        self._session.add(model)
        self._session.flush()
        return model.to_entity()

    def get_by_id(self, source_id: int) -> Source | None:
        model = self._session.get(SourceModel, source_id)
        return model.to_entity() if model else None

    def list_all(self) -> list[Source]:
        models = (
            self._session.query(SourceModel)
            .order_by(SourceModel.created_at.desc(), SourceModel.id)
            .all()
        )
        return [m.to_entity() for m in models]

    def get_first_by_role(self, role: SourceRole) -> Source | None:
        model = (
            self._session.query(SourceModel)
            .filter(SourceModel.role == role.value)
            .order_by(SourceModel.id)
            .first()
        )
        return model.to_entity() if model else None

    def update_title(self, source_id: int, title: str) -> None:
        model = self._session.get(SourceModel, source_id)
        if model is None:
            return
        model.title = title
        self._session.flush()

    def update_video_path(self, source_id: int, video_path: str | None) -> None:
        model = self._session.get(SourceModel, source_id)
        if model is None:
            from backend.domain.exceptions import SourceNotFoundError
            raise SourceNotFoundError(source_id)
        model.video_path = video_path
        self._session.flush()

    def set_collections(self, placements: Mapping[int, int | None]) -> None:
        for source_id, collection_id in placements.items():
            model = self._session.get(SourceModel, source_id)
            if model is None:
                from backend.domain.exceptions import SourceNotFoundError
                raise SourceNotFoundError(source_id)
            model.collection_id = collection_id
        self._session.flush()

    def delete(self, source_id: int) -> None:
        model = self._session.get(SourceModel, source_id)
        if model is None:
            return
        # The database cascade removes the source's words and phrases with it.
        lemmas = frozenset(self._session.scalars(
            select(StoredCandidateModel.lemma).where(StoredCandidateModel.source_id == source_id)
        ))
        self._session.delete(model)
        self._session.flush()
        if lemmas:
            self._recorder.record(SourceDeleted(source_id, lemmas))

    def get_title_map(self, source_ids: list[int]) -> dict[int, str]:
        if not source_ids:
            return {}
        models = (
            self._session.query(SourceModel.id, SourceModel.title)
            .filter(SourceModel.id.in_(source_ids))
            .all()
        )
        return {row.id: (row.title or "") for row in models}

    def update_status(
        self,
        source_id: int,
        status: SourceStatus,
        *,
        error_message: str | None = None,
    ) -> None:
        model = self._session.get(SourceModel, source_id)
        if model is None:
            return
        model.status = status.value
        if error_message is not None:
            model.error_message = error_message
        self._session.flush()
