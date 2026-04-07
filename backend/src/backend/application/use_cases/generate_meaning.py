from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.application.dto.ai_dtos import GenerateMeaningResponseDTO
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.exceptions import CandidateNotFoundError, PromptNotFoundError
from backend.domain.value_objects.enrichment_status import EnrichmentStatus

if TYPE_CHECKING:
    from backend.domain.ports.ai_service import AIService
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.prompt_repository import PromptRepository

_GENERATE_MEANING_KEY = "generate_meaning"


class GenerateMeaningUseCase:
    """Generates an AI-powered meaning for a word candidate and persists it."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        meaning_repo: CandidateMeaningRepository,
        ai_service: AIService,
        prompt_repo: PromptRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._meaning_repo = meaning_repo
        self._ai_service = ai_service
        self._prompt_repo = prompt_repo

    def execute(self, candidate_id: int) -> GenerateMeaningResponseDTO:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)

        prompt = self._prompt_repo.get_by_key(_GENERATE_MEANING_KEY)
        if prompt is None:
            raise PromptNotFoundError(_GENERATE_MEANING_KEY)

        user_prompt = prompt.user_template.format(
            lemma=candidate.lemma,
            pos=candidate.pos,
            context=candidate.context_fragment,
        )
        result = self._ai_service.generate_meaning(prompt.system_prompt, user_prompt)
        self._meaning_repo.upsert(CandidateMeaning(
            candidate_id=candidate_id,
            meaning=result.meaning,
            ipa=result.ipa,
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=datetime.now(tz=UTC),
        ))
        return GenerateMeaningResponseDTO(
            candidate_id=candidate_id,
            meaning=result.meaning,
            ipa=result.ipa,
            tokens_used=result.tokens_used,
        )
