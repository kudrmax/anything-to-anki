from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.card_report_dtos import CardReportDTO
from backend.domain.entities.card_report import CardReport
from backend.domain.exceptions import CandidateNotFoundError, EmptyReportCommentError

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.card_report_repository import CardReportRepository
    from backend.domain.ports.source_repository import SourceRepository

# Quick reasons offered next to the free-text comment.
REPORT_REASONS: tuple[str, ...] = (
    "Phrase too long",
    "Wrong phrase boundary",
    "More than one unknown word",
    "I know this word",
    "Not a real word",
    "Wrong word form",
)


class ReportCandidateUseCase:
    """Saves a complaint about a card together with a snapshot of the card."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
        report_repo: CardReportRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._source_repo = source_repo
        self._report_repo = report_repo

    def execute(self, candidate_id: int, comment: str) -> CardReportDTO:
        text = comment.strip()
        if not text:
            raise EmptyReportCommentError()
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None or candidate.id is None:
            raise CandidateNotFoundError(candidate_id)
        source = self._source_repo.get_by_id(candidate.source_id)
        saved = self._report_repo.add(CardReport(
            source_id=candidate.source_id,
            source_title=(source.title or "") if source else "",
            candidate_id=candidate.id,
            lemma=candidate.lemma,
            surface_form=candidate.surface_form,
            context_fragment=candidate.context_fragment,
            zipf_frequency=candidate.zipf_frequency,
            cefr_level=candidate.cefr_level,
            fragment_unknown_count=candidate.fragment_unknown_count,
            is_phrasal_verb=candidate.is_phrasal_verb,
            comment=text,
        ))
        return to_dto(saved)

    @staticmethod
    def reasons() -> list[str]:
        return list(REPORT_REASONS)

    def list_all(self) -> list[CardReportDTO]:
        return [to_dto(r) for r in self._report_repo.list_all()]


def to_dto(report: CardReport) -> CardReportDTO:
    assert report.id is not None and report.created_at is not None
    return CardReportDTO(
        id=report.id,
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
        comment=report.comment,
        created_at=report.created_at,
    )
