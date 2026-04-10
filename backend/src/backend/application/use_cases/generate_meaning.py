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


_FOLLOW_UP_ACTIONS: dict[str, str] = {
    "give_examples": (
        "The current definition is:\n{meaning}\n\n"
        "Give 2-3 more example sentences for this word. "
        "Each example on a new line. Bold the target word using **bold**. "
        "Use natural, everyday English at B1-B2 level."
    ),
    "explain_detail": (
        "The current definition is:\n{meaning}\n\n"
        "Explain this word in more detail. Go deeper into nuances, connotations, "
        "and typical usage patterns. Keep using simple English."
    ),
    "explain_simpler": (
        "The current definition is:\n{meaning}\n\n"
        "Explain this word much simpler — as if to a beginner. "
        "Use the simplest words possible, short sentences."
    ),
    "how_to_say": (
        "The current definition is:\n{meaning}\n\n"
        "Show how to use this word in a real conversation. "
        "Give 2-3 natural phrases or sentences people actually say. "
        "Each on a new line."
    ),
    "free_question": "{text}",
}

# Actions that REPLACE the meaning field; all others APPEND.
_REPLACE_ACTIONS: frozenset[str] = frozenset({
    "explain_detail",
    "explain_simpler",
    "free_question",
})

# Actions that target the examples field instead of meaning.
_EXAMPLES_ACTIONS: frozenset[str] = frozenset({
    "give_examples",
})


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
            examples=result.examples,
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
            examples=result.examples,
            ipa=result.ipa,
            tokens_used=result.tokens_used,
        )

    def execute_follow_up(
        self,
        candidate_id: int,
        action: str,
        text: str | None,
    ) -> GenerateMeaningResponseDTO:
        """Run a follow-up action on an existing meaning."""
        if action not in _FOLLOW_UP_ACTIONS:
            raise ValueError(f"Unknown follow-up action: {action}")
        if action == "free_question" and not text:
            raise ValueError("free_question action requires text")

        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)

        existing = self._meaning_repo.get_by_candidate_id(candidate_id)
        current_meaning = (existing.meaning if existing else None) or ""
        current_examples = (existing.examples if existing else None) or ""

        template = _FOLLOW_UP_ACTIONS[action]
        follow_up_prompt = template.format(
            meaning=current_meaning,
            text=text or "",
        )

        user_prompt = self._prompts_config.generate_meaning_user_template.format(
            lemma=candidate.lemma,
            pos=candidate.pos,
            context=candidate.context_fragment,
        )
        combined_prompt = f"{user_prompt}\n\n{follow_up_prompt}"

        result = self._ai_service.generate_meaning(
            self._prompts_config.generate_meaning_system, combined_prompt
        )

        # Decide how to apply result
        if action in _EXAMPLES_ACTIONS:
            # Append to examples
            new_examples = (
                f"{current_examples}\n{result.meaning}".strip()
                if current_examples
                else result.meaning
            )
            new_meaning = current_meaning
        elif action in _REPLACE_ACTIONS:
            new_meaning = result.meaning
            new_examples = current_examples
        else:
            # APPEND to meaning (how_to_say)
            new_meaning = (
                f"{current_meaning}\n{result.meaning}".strip()
                if current_meaning
                else result.meaning
            )
            new_examples = current_examples

        # Preserve existing fields that the follow-up didn't regenerate
        new_translation = (
            result.translation if not existing
            else (existing.translation or result.translation)
        )
        new_synonyms = (
            result.synonyms if not existing
            else (existing.synonyms or result.synonyms)
        )
        new_ipa = (
            result.ipa if not existing
            else (existing.ipa or result.ipa)
        )

        self._meaning_repo.upsert(CandidateMeaning(
            candidate_id=candidate_id,
            meaning=new_meaning,
            translation=new_translation,
            synonyms=new_synonyms,
            examples=new_examples,
            ipa=new_ipa,
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=datetime.now(tz=UTC),
        ))
        return GenerateMeaningResponseDTO(
            candidate_id=candidate_id,
            meaning=new_meaning,
            translation=new_translation or "",
            synonyms=new_synonyms or "",
            examples=new_examples,
            ipa=new_ipa,
            tokens_used=result.tokens_used,
        )
