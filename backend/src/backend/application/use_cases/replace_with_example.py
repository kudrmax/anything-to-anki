"""Use case: replace a candidate's phrase with one of its AI-generated examples."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import StoredCandidateDTO, stored_candidate_to_dto
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.services.topic_phrase_selection import parse_marked_phrase
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.domain.ports.candidate_repository import CandidateRepository


class ReplaceWithExampleUseCase:
    """Skip the current candidate and create a new one with a user-chosen example phrase.

    The example comes as AI wrote it: its **bold** words are the target; without them the
    target is found by the card's dictionary form.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        review_status: ReviewStatusUpdater,
        phrase_reader: PhraseReader,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._review_status = review_status
        self._phrase_reader = phrase_reader

    def execute(self, candidate_id: int, example_text: str) -> StoredCandidateDTO:
        stripped = example_text.strip()
        if not stripped:
            msg = "example_text must not be empty"
            raise ValueError(msg)

        original = self._candidate_repo.get_by_id(candidate_id)
        if original is None:
            raise CandidateNotFoundError(candidate_id)
        marked = parse_marked_phrase(stripped)
        phrase = (
            self._phrase_reader.read_for(marked.text, marked.target)
            if marked is not None
            else self._phrase_reader.read_for(stripped, original.lemma)
        )

        self._candidate_repo.update_status(candidate_id, CandidateStatus.SKIP)
        new_candidate = StoredCandidate(
            source_id=original.source_id,
            lemma=original.lemma,
            pos=original.pos,
            cefr_level=original.cefr_level,
            zipf_frequency=original.zipf_frequency,
            source_phrase=phrase,
            occurrences=1,
            status=CandidateStatus.PENDING,
            is_phrasal_verb=original.is_phrasal_verb,
            cefr_breakdown=original.cefr_breakdown,
            usage_distribution=original.usage_distribution,
        )
        saved = self._candidate_repo.create_batch([new_candidate])[0]
        self._review_status.refresh(original.source_id)
        return stored_candidate_to_dto(saved)
