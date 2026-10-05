from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import StoredCandidateDTO, stored_candidate_to_dto
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.exceptions import (
    CandidateNotFoundError,
    ClozeNotAllowedError,
    InvalidClozeError,
)
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind

if TYPE_CHECKING:
    from backend.application.use_cases.mark_candidate import MarkCandidateUseCase
    from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
    from backend.domain.ports.candidate_cloze_repository import CandidateClozeRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.card_report_repository import CardReportRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.services.cloze_builder import ClozeBuilder


class SaveClozeUseCase:
    """Saves which words of the phrase the cloze card hides and marks the candidate to learn."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        cloze_repo: CandidateClozeRepository,
        anki_sync_repo: AnkiSyncRepository,
        job_repo: JobRepository,
        report_repo: CardReportRepository,
        mark_candidate: MarkCandidateUseCase,
        builder: ClozeBuilder,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._cloze_repo = cloze_repo
        self._anki_sync_repo = anki_sync_repo
        self._job_repo = job_repo
        self._report_repo = report_repo
        self._mark_candidate = mark_candidate
        self._builder = builder

    def execute(
        self,
        candidate_id: int,
        hidden_word_indices: list[int],
        hint_kind: ClozeHintKind,
        custom_hint: str | None,
    ) -> StoredCandidateDTO:
        """Returns the candidate as it is after saving."""
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        if candidate_id in self._anki_sync_repo.get_synced_candidate_ids([candidate_id]):
            raise ClozeNotAllowedError(f"Candidate {candidate_id} is already in Anki")

        phrase = candidate.card_phrase
        indices = tuple(sorted(set(hidden_word_indices)))
        words = self._builder.words(phrase, candidate.lemma, candidate.surface_form)
        self._builder.validate(words, indices)
        custom = (custom_hint or "").strip()
        if hint_kind is ClozeHintKind.CUSTOM and not custom:
            raise InvalidClozeError("Write the hint")
        hidden = self._builder.hidden_words(phrase, indices)
        if hint_kind not in self._builder.available_hints(candidate.meaning, hidden):
            raise InvalidClozeError(
                f"The {hint_kind.value} hint is unavailable for the hidden words",
            )

        self._mark_candidate.apply(candidate, CandidateStatus.LEARN)
        self._cloze_repo.upsert(CandidateCloze(
            candidate_id=candidate_id,
            hidden_word_indices=indices,
            hint_kind=hint_kind,
            custom_hint=custom if hint_kind is ClozeHintKind.CUSTOM else None,
            phrase=phrase,
        ))
        saved = self._candidate_repo.get_by_id(candidate_id)
        assert saved is not None
        return stored_candidate_to_dto(
            saved,
            self._job_repo.get_jobs_for_candidates([candidate_id]),
            self._report_repo.reported_candidate_ids([candidate_id]),
            synced_ids=set(),
        )
