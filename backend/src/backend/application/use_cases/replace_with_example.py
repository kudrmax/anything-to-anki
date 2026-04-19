"""Use case: replace a candidate's phrase with one of its AI-generated examples."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import StoredCandidateDTO
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository


def _strip_bold(text: str) -> str:
    """Remove markdown bold markers: **word** → word."""
    return re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)


class ReplaceWithExampleUseCase:
    """Skip the current candidate and create a new one with a user-chosen example phrase."""

    def __init__(self, candidate_repo: CandidateRepository) -> None:
        self._candidate_repo = candidate_repo

    def execute(self, candidate_id: int, example_text: str) -> StoredCandidateDTO:
        stripped = example_text.strip()
        if not stripped:
            msg = "example_text must not be empty"
            raise ValueError(msg)

        original = self._candidate_repo.get_by_id(candidate_id)
        if original is None:
            raise CandidateNotFoundError(candidate_id)

        # Skip the old candidate
        self._candidate_repo.update_status(candidate_id, CandidateStatus.SKIP)

        # Create a new candidate with the chosen example as context_fragment
        new_candidate = StoredCandidate(
            source_id=original.source_id,
            lemma=original.lemma,
            pos=original.pos,
            cefr_level=original.cefr_level,
            zipf_frequency=original.zipf_frequency,
            context_fragment=_strip_bold(stripped),
            fragment_purity=original.fragment_purity,
            occurrences=1,
            status=CandidateStatus.PENDING,
            surface_form=None,
            is_phrasal_verb=original.is_phrasal_verb,
            has_custom_context_fragment=True,
        )
        saved = self._candidate_repo.create_batch([new_candidate])[0]

        return StoredCandidateDTO(
            id=saved.id,  # type: ignore[arg-type]
            lemma=saved.lemma,
            pos=saved.pos,
            cefr_level=saved.cefr_level,
            zipf_frequency=saved.zipf_frequency,
            is_sweet_spot=saved.is_sweet_spot,
            context_fragment=saved.context_fragment,
            fragment_purity=saved.fragment_purity,
            occurrences=saved.occurrences,
            status=saved.status.value,
            surface_form=saved.surface_form,
            is_phrasal_verb=saved.is_phrasal_verb,
            has_custom_context_fragment=saved.has_custom_context_fragment,
        )
