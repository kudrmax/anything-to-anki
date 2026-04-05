from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func

from backend.domain.ports.candidate_repository import CandidateRepository
from backend.infrastructure.persistence.models import StoredCandidateModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.candidate_status import CandidateStatus


class SqlaCandidateRepository(CandidateRepository):
    """SQLAlchemy implementation of CandidateRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_batch(self, candidates: list[StoredCandidate]) -> list[StoredCandidate]:
        models = [StoredCandidateModel.from_entity(c) for c in candidates]
        self._session.add_all(models)
        self._session.flush()
        return [m.to_entity() for m in models]

    def get_by_source(self, source_id: int) -> list[StoredCandidate]:
        models = (
            self._session.query(StoredCandidateModel)
            .filter(StoredCandidateModel.source_id == source_id)
            .all()
        )
        return [m.to_entity() for m in models]

    def get_by_id(self, candidate_id: int) -> StoredCandidate | None:
        model = self._session.get(StoredCandidateModel, candidate_id)
        return model.to_entity() if model else None

    def update_status(self, candidate_id: int, status: CandidateStatus) -> None:
        model = self._session.get(StoredCandidateModel, candidate_id)
        if model is not None:
            model.status = status.value
            self._session.flush()

    def count_by_status(self, status: CandidateStatus) -> int:
        result = (
            self._session.query(func.count(StoredCandidateModel.id))
            .filter(StoredCandidateModel.status == status.value)
            .scalar()
        )
        return result or 0

    def delete_by_source(self, source_id: int) -> None:
        self._session.query(StoredCandidateModel).filter(
            StoredCandidateModel.source_id == source_id
        ).delete()
        self._session.flush()
