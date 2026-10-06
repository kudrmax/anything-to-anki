from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.candidate_meaning_image_repository import (
    CandidateMeaningImageRepository,
)
from backend.infrastructure.persistence.models import CandidateMeaningImageModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage


class SqlaCandidateMeaningImageRepository(CandidateMeaningImageRepository):
    """SQLAlchemy implementation of CandidateMeaningImageRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_candidate_id(self, candidate_id: int) -> CandidateMeaningImage | None:
        model = self._session.get(CandidateMeaningImageModel, candidate_id)
        return model.to_entity() if model else None

    def upsert(self, image: CandidateMeaningImage) -> None:
        existing = self._session.get(CandidateMeaningImageModel, image.candidate_id)
        if existing is None:
            self._session.add(CandidateMeaningImageModel.from_entity(image))
        else:
            existing.image_path = image.image_path
        self._session.flush()

    def delete_by_candidate_id(self, candidate_id: int) -> None:
        model = self._session.get(CandidateMeaningImageModel, candidate_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
