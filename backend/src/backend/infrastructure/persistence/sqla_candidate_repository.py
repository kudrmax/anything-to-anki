from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func

from backend.domain.ports.candidate_repository import CandidateRepository
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.models import StoredCandidateModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.stored_candidate import StoredCandidate


_ACTIVE_STATUSES: list[str] = [CandidateStatus.PENDING.value, CandidateStatus.LEARN.value]


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

    def update_meaning(self, candidate_id: int, meaning: str) -> None:
        model = self._session.get(StoredCandidateModel, candidate_id)
        if model is not None:
            model.meaning = meaning
            self._session.flush()

    def update_meaning_and_ipa(self, candidate_id: int, meaning: str, ipa: str | None) -> None:
        model = self._session.get(StoredCandidateModel, candidate_id)
        if model is not None:
            model.meaning = meaning
            model.ipa = ipa
            self._session.flush()

    def update_context_fragment(self, candidate_id: int, context_fragment: str) -> None:
        model = self._session.get(StoredCandidateModel, candidate_id)
        if model is not None:
            model.context_fragment = context_fragment
            self._session.flush()

    def get_without_meaning(self, source_id: int | None, limit: int) -> list[StoredCandidate]:
        query = self._session.query(StoredCandidateModel).filter(
            StoredCandidateModel.meaning.is_(None)
        )
        if source_id is not None:
            query = query.filter(StoredCandidateModel.source_id == source_id)
        query = query.order_by(
            StoredCandidateModel.is_sweet_spot.desc(),
            StoredCandidateModel.cefr_level.desc(),
        )
        return [m.to_entity() for m in query.limit(limit).all()]

    def count_without_meaning(self, source_id: int | None) -> int:
        query = self._session.query(func.count(StoredCandidateModel.id)).filter(
            StoredCandidateModel.meaning.is_(None)
        )
        if source_id is not None:
            query = query.filter(StoredCandidateModel.source_id == source_id)
        return query.scalar() or 0

    def get_active_without_meaning(self, source_id: int | None, limit: int) -> list[StoredCandidate]:
        query = self._session.query(StoredCandidateModel).filter(
            StoredCandidateModel.meaning.is_(None),
            StoredCandidateModel.status.in_(_ACTIVE_STATUSES),
        )
        if source_id is not None:
            query = query.filter(StoredCandidateModel.source_id == source_id)
        query = query.order_by(
            StoredCandidateModel.is_sweet_spot.desc(),
            StoredCandidateModel.cefr_level.desc(),
        )
        return [m.to_entity() for m in query.limit(limit).all()]

    def count_active_without_meaning(self, source_id: int | None) -> int:
        query = self._session.query(func.count(StoredCandidateModel.id)).filter(
            StoredCandidateModel.meaning.is_(None),
            StoredCandidateModel.status.in_(_ACTIVE_STATUSES),
        )
        if source_id is not None:
            query = query.filter(StoredCandidateModel.source_id == source_id)
        return query.scalar() or 0

    def get_by_ids(self, candidate_ids: list[int]) -> list[StoredCandidate]:
        if not candidate_ids:
            return []
        models = (
            self._session.query(StoredCandidateModel)
            .filter(StoredCandidateModel.id.in_(candidate_ids))
            .all()
        )
        # Preserve order from candidate_ids list
        order_map = {cid: idx for idx, cid in enumerate(candidate_ids)}
        models.sort(key=lambda m: order_map.get(m.id, 999999))
        return [m.to_entity() for m in models]

    def get_all_active_without_meaning(self, source_id: int | None) -> list[StoredCandidate]:
        query = self._session.query(StoredCandidateModel).filter(
            StoredCandidateModel.meaning.is_(None),
            StoredCandidateModel.status.in_(_ACTIVE_STATUSES),
        )
        if source_id is not None:
            query = query.filter(StoredCandidateModel.source_id == source_id)
        query = query.order_by(
            StoredCandidateModel.is_sweet_spot.desc(),
            StoredCandidateModel.cefr_level.desc(),
        )
        return [m.to_entity() for m in query.all()]

    def delete_by_source(self, source_id: int) -> None:
        self._session.query(StoredCandidateModel).filter(
            StoredCandidateModel.source_id == source_id
        ).delete()
        self._session.flush()
