from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.domain.ports.card_report_repository import CardReportRepository
from backend.infrastructure.persistence.models import CardReportModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.card_report import CardReport


class SqlaCardReportRepository(CardReportRepository):
    """SQLAlchemy implementation of CardReportRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, report: CardReport) -> CardReport:
        model = CardReportModel(
            source_id=report.source_id,
            source_title=report.source_title,
            candidate_id=report.candidate_id,
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
        return model.to_entity()

    def list_all(self) -> list[CardReport]:
        models = (
            self._session.query(CardReportModel)
            .order_by(CardReportModel.created_at.desc(), CardReportModel.id.desc())
            .all()
        )
        return [m.to_entity() for m in models]

    def reported_candidate_ids(self, candidate_ids: list[int]) -> set[int]:
        if not candidate_ids:
            return set()
        rows = (
            self._session.query(CardReportModel.candidate_id)
            .filter(CardReportModel.candidate_id.in_(candidate_ids))
            .distinct()
            .all()
        )
        return {row[0] for row in rows}
