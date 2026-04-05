from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.ai_dtos import GenerateMeaningResponseDTO
from backend.domain.exceptions import CandidateNotFoundError

if TYPE_CHECKING:
    from backend.domain.ports.ai_service import AIService
    from backend.domain.ports.candidate_repository import CandidateRepository


class GenerateMeaningUseCase:
    """Generates an AI-powered meaning for a word candidate and persists it."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        ai_service: AIService,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._ai_service = ai_service

    def execute(self, candidate_id: int) -> GenerateMeaningResponseDTO:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)

        result = self._ai_service.generate_meaning(
            lemma=candidate.lemma,
            pos=candidate.pos,
            context=candidate.context_fragment,
        )
        self._candidate_repo.update_ai_meaning(candidate_id, result.meaning)
        return GenerateMeaningResponseDTO(
            candidate_id=candidate_id,
            meaning=result.meaning,
            tokens_used=result.tokens_used,
        )
