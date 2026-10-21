from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.domain.ports.card_report_repository import CardReportRepository
from backend.domain.value_objects.card_change import CardContentChanged
from backend.infrastructure.persistence.models import CardReportModel
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.card_report import CardReport
    from backend.domain.ports.change_recorder import ChangeRecorder


class SqlaCardReportRepository(CardReportRepository):
    """SQLAlchemy implementation of CardReportRepository. A card shows whether it was
    reported: a new report records its phrase's content changed."""

    def __init__(self, session: Session, recorder: ChangeRecorder) -> None:
        self._session = session
        self._recorder = recorder

    def add(self, report: CardReport) -> CardReport:
        model = CardReportModel(
            source_id=report.source_id,
            source_title=report.source_title,
            candidate_id=report.candidate_id,
            phrase_id=report.phrase_id,
            lemma=report.lemma,
            surface_form=report.surface_form,
            context_fragment=report.context_fragment,
            zipf_frequency=report.zipf_frequency,
            cefr_level=report.cefr_level,
            fragment_unknown_count=report.fragment_unknown_count,
            is_phrasal_verb=report.is_phrasal_verb,
            reasons=json.dumps(list(report.reasons)),
            comment=report.comment,
            text_before=report.text_before,
            text_after=report.text_after,
        )
        self._session.add(model)
        self._session.flush()
        if report.phrase_id is not None:
            self._recorder.record(CardContentChanged(report.phrase_id))
        return model.to_entity()

    def list_all(self) -> list[CardReport]:
        models = (
            self._session.query(CardReportModel)
            .order_by(CardReportModel.created_at.desc(), CardReportModel.id.desc())
            .all()
        )
        return [m.to_entity() for m in models]

    def reported_phrase_ids(self, phrase_ids: list[int]) -> set[int]:
        found: set[int] = set()
        for chunk in chunks(phrase_ids):
            found.update(self._session.scalars(
                select(CardReportModel.phrase_id)
                .where(CardReportModel.phrase_id.in_(chunk))
                .distinct()
            ))
        return found
