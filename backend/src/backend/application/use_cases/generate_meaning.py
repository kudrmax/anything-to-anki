from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.application.dto.ai_dtos import GenerateMeaningResponseDTO
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.value_objects.enrichment_status import EnrichmentStatus

if TYPE_CHECKING:
    from backend.domain.ports.ai_service import AIService
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.value_objects.prompts_config import PromptsConfig


class GenerateMeaningUseCase:
    """Generates an AI-powered meaning for a word candidate and persists it."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        meaning_repo: CandidateMeaningRepository,
        ai_service: AIService,
        prompts_config: PromptsConfig,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._meaning_repo = meaning_repo
        self._ai_service = ai_service
        self._prompts_config = prompts_config

    def execute(self, candidate_id: int) -> GenerateMeaningResponseDTO:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)

        user_prompt = self._prompts_config.generate_meaning_user_template.format(
            lemma=candidate.lemma,
            pos=candidate.pos,
            context=candidate.context_fragment,
        )
        result = self._ai_service.generate_meaning(
            self._prompts_config.generate_meaning_system, user_prompt
        )
        self._meaning_repo.upsert(CandidateMeaning(
            candidate_id=candidate_id,
            meaning=result.meaning,
            translation=result.translation,
            synonyms=result.synonyms,
            ipa=result.ipa,
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=datetime.now(tz=UTC),
        ))
        return GenerateMeaningResponseDTO(
            candidate_id=candidate_id,
            meaning=result.meaning,
            translation=result.translation,
            synonyms=result.synonyms,
            ipa=result.ipa,
            tokens_used=result.tokens_used,
        )
