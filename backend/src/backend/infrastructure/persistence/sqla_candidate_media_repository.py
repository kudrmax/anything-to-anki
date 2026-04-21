from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.models import (
    CandidateMediaModel,
    StoredCandidateModel,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_media import CandidateMedia


class SqlaCandidateMediaRepository(CandidateMediaRepository):
    """SQLAlchemy implementation of CandidateMediaRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_candidate_id(self, candidate_id: int) -> CandidateMedia | None:
        model = self._session.get(CandidateMediaModel, candidate_id)
        return model.to_entity() if model else None

    def get_all_by_source(self, source_id: int) -> dict[int, CandidateMedia]:
        stmt = (
            select(CandidateMediaModel)
            .join(
                StoredCandidateModel,
                StoredCandidateModel.id == CandidateMediaModel.candidate_id,
            )
            .where(StoredCandidateModel.source_id == source_id)
        )
        rows = self._session.execute(stmt).scalars().all()
        return {row.candidate_id: row.to_entity() for row in rows}

    def get_all_by_source_id(self, source_id: int) -> list[CandidateMedia]:
        stmt = (
            select(CandidateMediaModel)
            .join(
                StoredCandidateModel,
                StoredCandidateModel.id == CandidateMediaModel.candidate_id,
            )
            .where(StoredCandidateModel.source_id == source_id)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [row.to_entity() for row in rows]

    def get_by_candidate_ids(self, candidate_ids: list[int]) -> dict[int, CandidateMedia]:
        if not candidate_ids:
            return {}
        stmt = select(CandidateMediaModel).where(
            CandidateMediaModel.candidate_id.in_(candidate_ids)
        )
        rows = self._session.execute(stmt).scalars().all()
        return {row.candidate_id: row.to_entity() for row in rows}

    def upsert(self, media: CandidateMedia) -> None:
        existing = self._session.get(CandidateMediaModel, media.candidate_id)
        if existing is None:
            self._session.add(CandidateMediaModel.from_entity(media))
        else:
            existing.screenshot_path = media.screenshot_path
            existing.audio_path = media.audio_path
            existing.start_ms = media.start_ms
            existing.end_ms = media.end_ms
            existing.generated_at = media.generated_at
        self._session.flush()

    def clear_paths(
        self,
        candidate_id: int,
        *,
        clear_screenshot: bool,
        clear_audio: bool,
    ) -> None:
        values: dict[str, None] = {}
        if clear_screenshot:
            values["screenshot_path"] = None
        if clear_audio:
            values["audio_path"] = None
        if not values:
            return
        self._session.execute(
            update(CandidateMediaModel)
            .where(CandidateMediaModel.candidate_id == candidate_id)
            .values(**values)
        )
        self._session.flush()

    def get_eligible_candidate_ids(
        self,
        source_id: int,
    ) -> list[int]:
        stmt = (
            select(StoredCandidateModel.id)
            .join(
                CandidateMediaModel,
                CandidateMediaModel.candidate_id == StoredCandidateModel.id,
            )
            .where(
                StoredCandidateModel.source_id == source_id,
                StoredCandidateModel.status.in_(
                    [CandidateStatus.PENDING.value, CandidateStatus.LEARN.value]
                ),
                CandidateMediaModel.start_ms.is_not(None),
                CandidateMediaModel.end_ms.is_not(None),
                CandidateMediaModel.screenshot_path.is_(None),
            )
        )
        rows = self._session.execute(stmt).all()
        return [row[0] for row in rows]
