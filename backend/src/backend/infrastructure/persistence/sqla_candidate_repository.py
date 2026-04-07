# backend/src/backend/infrastructure/persistence/sqla_candidate_repository.py
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func

from backend.domain.ports.candidate_repository import CandidateRepository
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.models import (
    CandidateMeaningModel,
    CandidateMediaModel,
    StoredCandidateModel,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.stored_candidate import StoredCandidate


class SqlaCandidateRepository(CandidateRepository):
    """SQLAlchemy implementation of CandidateRepository.

    On read methods, attaches `meaning` and `media` from sibling tables in a
    single follow-up query (one per kind, by candidate_id IN (...)).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_batch(self, candidates: list[StoredCandidate]) -> list[StoredCandidate]:
        models = [StoredCandidateModel.from_entity(c) for c in candidates]
        self._session.add_all(models)
        self._session.flush()
        # Fresh candidates never have enrichments yet — skip the lookup.
        return [m.to_entity() for m in models]

    def get_by_source(self, source_id: int) -> list[StoredCandidate]:
        models = (
            self._session.query(StoredCandidateModel)
            .filter(StoredCandidateModel.source_id == source_id)
            .all()
        )
        entities = [m.to_entity() for m in models]
        return self._bulk_attach(entities)

    def get_by_id(self, candidate_id: int) -> StoredCandidate | None:
        model = self._session.get(StoredCandidateModel, candidate_id)
        if model is None:
            return None
        return self._attach_enrichments(model.to_entity())

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

    def update_context_fragment(self, candidate_id: int, context_fragment: str) -> None:
        model = self._session.get(StoredCandidateModel, candidate_id)
        if model is not None:
            model.context_fragment = context_fragment
            self._session.flush()

    def get_by_ids(self, candidate_ids: list[int]) -> list[StoredCandidate]:
        if not candidate_ids:
            return []
        models = (
            self._session.query(StoredCandidateModel)
            .filter(StoredCandidateModel.id.in_(candidate_ids))
            .all()
        )
        order_map = {cid: idx for idx, cid in enumerate(candidate_ids)}
        models.sort(key=lambda m: order_map.get(m.id, 999999))
        entities = [m.to_entity() for m in models]
        return self._bulk_attach(entities)

    def delete_by_source(self, source_id: int) -> None:
        # Find candidate ids first to also delete their enrichment rows
        cid_rows = (
            self._session.query(StoredCandidateModel.id)
            .filter(StoredCandidateModel.source_id == source_id)
            .all()
        )
        cids = [r[0] for r in cid_rows]
        if cids:
            self._session.query(CandidateMeaningModel).filter(
                CandidateMeaningModel.candidate_id.in_(cids)
            ).delete(synchronize_session=False)
            self._session.query(CandidateMediaModel).filter(
                CandidateMediaModel.candidate_id.in_(cids)
            ).delete(synchronize_session=False)
        self._session.query(StoredCandidateModel).filter(
            StoredCandidateModel.source_id == source_id
        ).delete()
        self._session.flush()

    def get_active_without_meaning(
        self, source_id: int, limit: int
    ) -> list[StoredCandidate]:
        active_statuses = (CandidateStatus.PENDING.value, CandidateStatus.LEARN.value)
        models = (
            self._session.query(StoredCandidateModel)
            .outerjoin(
                CandidateMeaningModel,
                CandidateMeaningModel.candidate_id == StoredCandidateModel.id,
            )
            .filter(
                StoredCandidateModel.source_id == source_id,
                StoredCandidateModel.status.in_(active_statuses),
                CandidateMeaningModel.candidate_id.is_(None),
            )
            .limit(limit)
            .all()
        )
        entities = [m.to_entity() for m in models]
        return self._bulk_attach(entities)

    def count_active_without_meaning(self, source_id: int) -> int:
        active_statuses = (CandidateStatus.PENDING.value, CandidateStatus.LEARN.value)
        result = (
            self._session.query(func.count(StoredCandidateModel.id))
            .outerjoin(
                CandidateMeaningModel,
                CandidateMeaningModel.candidate_id == StoredCandidateModel.id,
            )
            .filter(
                StoredCandidateModel.source_id == source_id,
                StoredCandidateModel.status.in_(active_statuses),
                CandidateMeaningModel.candidate_id.is_(None),
            )
            .scalar()
        )
        return result or 0

    # ── private helpers ────────────────────────────────────────────────

    def _attach_enrichments(self, entity: StoredCandidate) -> StoredCandidate:
        if entity.id is None:
            return entity
        meaning_model = self._session.get(CandidateMeaningModel, entity.id)
        media_model = self._session.get(CandidateMediaModel, entity.id)
        entity.meaning = meaning_model.to_entity() if meaning_model else None
        entity.media = media_model.to_entity() if media_model else None
        return entity

    def _bulk_attach(self, entities: list[StoredCandidate]) -> list[StoredCandidate]:
        ids = [e.id for e in entities if e.id is not None]
        if not ids:
            return entities
        meaning_rows = (
            self._session.query(CandidateMeaningModel)
            .filter(CandidateMeaningModel.candidate_id.in_(ids))
            .all()
        )
        media_rows = (
            self._session.query(CandidateMediaModel)
            .filter(CandidateMediaModel.candidate_id.in_(ids))
            .all()
        )
        meanings = {r.candidate_id: r.to_entity() for r in meaning_rows}
        medias = {r.candidate_id: r.to_entity() for r in media_rows}
        for e in entities:
            if e.id is not None:
                e.meaning = meanings.get(e.id)
                e.media = medias.get(e.id)
        return entities
