from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.source_repository import SourceRepository
from backend.infrastructure.persistence.models import SourceModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.source import Source
    from backend.domain.value_objects.processing_stage import ProcessingStage
    from backend.domain.value_objects.source_status import SourceStatus


class SqlaSourceRepository(SourceRepository):
    """SQLAlchemy implementation of SourceRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, source: Source) -> Source:
        model = SourceModel.from_entity(source)
        self._session.add(model)
        self._session.flush()
        return model.to_entity()

    def get_by_id(self, source_id: int) -> Source | None:
        model = self._session.get(SourceModel, source_id)
        return model.to_entity() if model else None

    def list_all(self) -> list[Source]:
        models = self._session.query(SourceModel).order_by(SourceModel.created_at.desc()).all()
        return [m.to_entity() for m in models]

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

    def delete(self, source_id: int) -> None:
        model = self._session.get(SourceModel, source_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    def update_status(
        self,
        source_id: int,
        status: SourceStatus,
        *,
        cleaned_text: str | None = None,
        error_message: str | None = None,
        processing_stage: ProcessingStage | None = None,
    ) -> None:
        model = self._session.get(SourceModel, source_id)
        if model is None:
            return
        model.status = status.value
        model.processing_stage = processing_stage.value if processing_stage else None
        if cleaned_text is not None:
            model.cleaned_text = cleaned_text
        if error_message is not None:
            model.error_message = error_message
        self._session.flush()
