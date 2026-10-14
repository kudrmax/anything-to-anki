from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import StoredCandidateDTO, stored_candidate_to_dto
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.exceptions import (
    ClozeNotAllowedError,
    ClozePhraseChangedError,
    InvalidClozeError,
    PhraseNotFoundError,
)
from backend.domain.services.card_decision import DecisionAction
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind

if TYPE_CHECKING:
    from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
    from backend.domain.ports.candidate_cloze_repository import CandidateClozeRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.card_report_repository import CardReportRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.services.cloze_builder import ClozeBuilder


class SaveClozeUseCase:
    """Saves which words of the phrase the cloze card hides: Cloze decided on the phrase."""

    def __init__(
        self,
        occurrence_repo: OccurrenceRepository,
        candidate_repo: CandidateRepository,
        cloze_repo: CandidateClozeRepository,
        job_repo: JobRepository,
        report_repo: CardReportRepository,
        decide_phrase: DecidePhraseUseCase,
        builder: ClozeBuilder,
    ) -> None:
        self._occurrences = occurrence_repo
        self._candidate_repo = candidate_repo
        self._cloze_repo = cloze_repo
        self._job_repo = job_repo
        self._report_repo = report_repo
        self._decide_phrase = decide_phrase
        self._builder = builder

    def execute(
        self,
        occurrence_id: int,
        phrase: str,
        hidden_word_indices: list[int],
        hint_kind: ClozeHintKind,
        custom_hint: str | None,
    ) -> StoredCandidateDTO:
        """Returns the word as it is after saving.

        `phrase` is the card phrase the user picked the words in: if the card shows another
        one by now (polish landed or was reverted), the indices point at other words."""
        occ = self._occurrences.get(occurrence_id)
        if occ is None:
            raise PhraseNotFoundError(occurrence_id)
        if occ.exported:
            raise ClozeNotAllowedError(f"Phrase {occurrence_id} is already in Anki")

        if phrase != occ.phrase.text:
            raise ClozePhraseChangedError(occurrence_id)
        indices = tuple(sorted(set(hidden_word_indices)))
        self._builder.validate(occ.phrase, indices)
        custom = (custom_hint or "").strip()
        if hint_kind is ClozeHintKind.CUSTOM and not custom:
            raise InvalidClozeError("Write the hint")
        hidden = self._builder.hidden_words(occ.phrase, indices)
        if hint_kind not in self._builder.available_hints(occ.meaning, hidden):
            raise InvalidClozeError(
                f"The {hint_kind.value} hint is unavailable for the hidden words",
            )

        self._decide_phrase.execute(occurrence_id, DecisionAction.CLOZE)
        self._cloze_repo.upsert_for_phrase(occurrence_id, CandidateCloze(
            candidate_id=occ.candidate_id,
            hidden_word_indices=indices,
            hint_kind=hint_kind,
            custom_hint=custom if hint_kind is ClozeHintKind.CUSTOM else None,
            phrase=phrase,
        ))
        word_id = occ.candidate_id
        saved = self._candidate_repo.get_by_id(word_id)
        assert saved is not None
        return stored_candidate_to_dto(
            saved,
            self._job_repo.get_jobs_for_candidates([word_id]),
            self._report_repo.reported_candidate_ids([word_id]),
            synced_ids=set(),
        )
