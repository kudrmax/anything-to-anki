from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.card_report_dtos import CardReportDTO
from backend.domain.entities.card_report import CardReport
from backend.domain.exceptions import (
    CandidateNotFoundError,
    EmptyReportCommentError,
    UnknownReportReasonError,
)
from backend.domain.value_objects.fragment_surroundings import FragmentSurroundings

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
    "I don't understand the grammar",
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

    def execute(self, candidate_id: int, reasons: list[str], comment: str) -> CardReportDTO:
        comment_text = comment.strip()
        chosen = tuple(dict.fromkeys(reasons))
        for reason in chosen:
            if reason not in REPORT_REASONS:
                raise UnknownReportReasonError(reason)
        if not chosen and not comment_text:
            raise EmptyReportCommentError()
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None or candidate.id is None:
            raise CandidateNotFoundError(candidate_id)
        source = self._source_repo.get_by_id(candidate.source_id)
        text = source.searchable_text if source else None
        around = FragmentSurroundings.find(text, candidate.context_fragment) if text else None
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
            reasons=chosen,
            comment=comment_text,
            text_before=around.before if around else None,
            text_after=around.after if around else None,
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
        reasons=list(report.reasons),
        comment=report.comment,
        text_before=report.text_before,
        text_after=report.text_after,
        created_at=report.created_at,
    )
