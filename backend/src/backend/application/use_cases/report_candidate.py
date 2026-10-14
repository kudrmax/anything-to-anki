from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.card_report_dtos import CardReportDTO, ReportReasonDTO
from backend.domain.entities.card_report import CardReport
from backend.domain.exceptions import (
    EmptyReportCommentError,
    PhraseNotFoundError,
    UnknownReportReasonError,
)
from backend.domain.services.candidate_sections import new_words
from backend.domain.value_objects.fragment_surroundings import FragmentSurroundings

if TYPE_CHECKING:
    from backend.application.dto.card_report_dtos import ReportCandidateRequest
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.application.utils.user_knowledge_reader import UserKnowledgeReader
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.card_report_repository import CardReportRepository
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.phrase import Phrase

# The reason under which the user picks the words of the phrase they don't know.
UNKNOWN_WORDS_REASON = "More than one unknown word"
# Quick reasons offered next to the free-text comment.
REPORT_REASONS: tuple[str, ...] = (
    "Phrase too long",
    "Wrong phrase boundary",
    UNKNOWN_WORDS_REASON,
    "I know this word",
    "Not a real word",
    "Wrong word form",
    "I don't understand the grammar",
)


class ReportCandidateUseCase:
    """Saves a complaint about a card — a shown phrase — together with a snapshot of it.

    Words of the phrase the user marked as not known go to their unknown words:
    every card with them moves out of Ready.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        occurrence_repo: OccurrenceRepository,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        report_repo: CardReportRepository,
        vocabulary: UserVocabulary,
        knowledge: UserKnowledgeReader,
        review_status: ReviewStatusUpdater,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._occurrences = occurrence_repo
        self._document_repo = document_repo
        self._source_repo = source_repo
        self._report_repo = report_repo
        self._vocabulary = vocabulary
        self._knowledge = knowledge
        self._review_status = review_status

    def execute(self, phrase_id: int, request: ReportCandidateRequest) -> CardReportDTO:
        comment_text = request.comment.strip()
        chosen = tuple(dict.fromkeys(request.reasons))
        for reason in chosen:
            if reason not in REPORT_REASONS:
                raise UnknownReportReasonError(reason)
        if not chosen and not comment_text and not request.unknown_words:
            raise EmptyReportCommentError()
        occ = self._occurrences.get(phrase_id)
        word = self._candidate_repo.get_by_id(occ.candidate_id) if occ is not None else None
        if occ is None or word is None or word.id is None:
            raise PhraseNotFoundError(phrase_id)
        new = new_words(occ.phrase, self._knowledge.current())
        source = self._source_repo.get_by_id(word.source_id)
        around = FragmentSurroundings.around(
            self._document_repo.get(word.source_id), occ.phrase_position,
        )
        saved = self._report_repo.add(CardReport(
            source_id=word.source_id,
            source_title=(source.title or "") if source else "",
            candidate_id=word.id,
            lemma=word.lemma,
            surface_form=occ.phrase.target_text(),
            context_fragment=occ.phrase.text,
            zipf_frequency=word.zipf_frequency,
            cefr_level=word.cefr_level,
            fragment_unknown_count=len(new),
            is_phrasal_verb=word.is_phrasal_verb,
            reasons=chosen,
            comment=comment_text,
            text_before=around.before if around else None,
            text_after=around.after if around else None,
            phrase_id=phrase_id,
        ))
        self._mark_unknown(occ.phrase, request.unknown_words)
        return to_dto(saved)

    def _mark_unknown(self, phrase: Phrase, indices: list[int]) -> None:
        lemmas = list(dict.fromkeys(
            phrase.words[i].lemma for i in indices if 0 <= i < len(phrase.words)
        ))
        for lemma in lemmas:
            self._vocabulary.mark_unknown(lemma)
        if lemmas:
            self._review_status.refresh_all()

    @staticmethod
    def reasons() -> list[ReportReasonDTO]:
        return [
            ReportReasonDTO(label=reason, picks_words=reason == UNKNOWN_WORDS_REASON)
            for reason in REPORT_REASONS
        ]

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
