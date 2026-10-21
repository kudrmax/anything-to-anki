from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.candidate_meaning_image_repository import (
    CandidateMeaningImageRepository,
)
from backend.domain.value_objects.card_change import WordContentChanged
from backend.infrastructure.persistence.models import CandidateMeaningImageModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
    from backend.domain.ports.change_recorder import ChangeRecorder


class SqlaCandidateMeaningImageRepository(CandidateMeaningImageRepository):
    """SQLAlchemy implementation of CandidateMeaningImageRepository."""

    def __init__(self, session: Session, recorder: ChangeRecorder) -> None:
        self._session = session
        self._recorder = recorder

    def upsert(self, image: CandidateMeaningImage) -> None:
        existing = self._session.get(CandidateMeaningImageModel, image.candidate_id)
        if existing is None:
            self._session.add(CandidateMeaningImageModel.from_entity(image))
        else:
            existing.image_path = image.image_path
        self._session.flush()
        self._recorder.record(WordContentChanged(image.candidate_id))

    def delete_by_candidate_id(self, candidate_id: int) -> None:
        model = self._session.get(CandidateMeaningImageModel, candidate_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
            self._recorder.record(WordContentChanged(candidate_id))
