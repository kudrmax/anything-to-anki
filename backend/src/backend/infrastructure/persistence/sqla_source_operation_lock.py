from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CursorResult, delete, insert, select, update

from backend.domain.ports.source_operation_lock import SourceOperationLock
from backend.domain.value_objects.held_operation import HeldOperation
from backend.domain.value_objects.processing_stage import ProcessingStage
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.persistence.models import SourceOperationModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SqlaSourceOperationLock(SourceOperationLock):
    """SQLAlchemy implementation of SourceOperationLock: one row per busy source."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def acquire(self, source_id: int, kind: SourceOperationKind) -> bool:
        result: CursorResult[tuple[()]] = self._session.execute(  # type: ignore[assignment]
            insert(SourceOperationModel)
            .prefix_with("OR IGNORE")
            .values(source_id=source_id, kind=kind.value, started_at=datetime.now(tz=UTC))
        )
        self._session.flush()
        return result.rowcount == 1

    def release(self, source_id: int) -> None:
        self._session.execute(
            delete(SourceOperationModel).where(SourceOperationModel.source_id == source_id)
        )
        self._session.flush()

    def held(self, source_id: int) -> SourceOperationKind | None:
        kind = self._session.scalar(
            select(SourceOperationModel.kind).where(SourceOperationModel.source_id == source_id)
        )
        return SourceOperationKind(kind) if kind is not None else None

    def set_stage(self, source_id: int, stage: ProcessingStage) -> None:
        self._session.execute(
            update(SourceOperationModel)
            .where(SourceOperationModel.source_id == source_id)
            .values(stage=stage.value)
        )
        self._session.flush()

    def operations(self) -> dict[int, HeldOperation]:
        rows = self._session.execute(
            select(
                SourceOperationModel.source_id,
                SourceOperationModel.kind,
                SourceOperationModel.stage,
            )
        ).all()
        return {
            source_id: HeldOperation(
                kind=SourceOperationKind(kind),
                stage=ProcessingStage(stage) if stage is not None else None,
            )
            for source_id, kind, stage in rows
        }

    def clear_all(self) -> None:
        self._session.execute(delete(SourceOperationModel))
        self._session.flush()
