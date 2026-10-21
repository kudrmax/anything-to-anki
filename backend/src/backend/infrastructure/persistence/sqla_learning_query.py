from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from backend.domain.ports.learning_query import LearningQuery
from backend.domain.value_objects.learning_timer import exported_for_due
from backend.infrastructure.persistence.models import (
    AnkiSyncedCardModel,
    PhraseModel,
    StoredCandidateModel,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from sqlalchemy.orm import Session


class SqlaLearningQuery(LearningQuery):
    """Learn words of every source not exported yet (their decision status is LEARN), and
    the active bindings of `anki_synced_cards`, including those whose card or source is
    gone. Read from the facts: the rules read this, the projection is built from them."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def awaiting_export(self) -> frozenset[str]:
        return frozenset(self._session.scalars(
            select(func.lower(StoredCandidateModel.lemma))
            .join(PhraseModel, PhraseModel.candidate_id == StoredCandidateModel.id)
            .where(PhraseModel.awaits_export())
            .distinct()
        ))

    def timers_due_between(self, after: datetime | None, until: datetime) -> frozenset[str]:
        since = AnkiSyncedCardModel.learning_since
        exported_after, exported_by = exported_for_due(after, until)
        window = [since <= exported_by]
        if exported_after is not None:
            window.append(since > exported_after)
        return frozenset(self._session.scalars(
            select(func.lower(AnkiSyncedCardModel.lemma))
            .where(AnkiSyncedCardModel.released_at.is_(None), *window)
            .distinct()
        ))

    def active_since(self) -> Mapping[str, tuple[datetime, ...]]:
        since: dict[str, list[datetime]] = {}
        for lemma, learning_since in self._session.execute(
            select(func.lower(AnkiSyncedCardModel.lemma), AnkiSyncedCardModel.learning_since)
            .where(AnkiSyncedCardModel.released_at.is_(None))
            .order_by(AnkiSyncedCardModel.id)
        ):
            since.setdefault(lemma, []).append(learning_since)
        return {lemma: tuple(dates) for lemma, dates in since.items()}
