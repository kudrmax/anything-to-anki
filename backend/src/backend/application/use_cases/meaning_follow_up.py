from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.exceptions import PhraseChangedError

if TYPE_CHECKING:
    from backend.application.utils.generation_targets import GenerationCard
    from backend.application.utils.requested_cards import RequestedCards
    from backend.domain.ports.ai_service import AIService
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.meaning_follow_up import MeaningFollowUp
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


def check_follow_up(follow_up: MeaningFollowUp) -> None:
    """Raise ValueError for a follow-up no AI call can answer."""
    if follow_up.action not in _FOLLOW_UP_ACTIONS:
        raise ValueError(f"Unknown follow-up action: {follow_up.action}")
    if follow_up.action == "free_question" and not follow_up.text:
        raise ValueError("free_question action requires text")


class MeaningFollowUpUseCase:
    """Answers a follow-up about the meaning of one phrase and stores the result there.
    Runs in the worker: the request only queues it."""

    def __init__(
        self,
        cards: RequestedCards,
        occurrence_repo: OccurrenceRepository,
        meaning_repo: CandidateMeaningRepository,
        ai_service: AIService,
        prompts_config: PromptsConfig,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._cards = cards
        self._occurrence_repo = occurrence_repo
        self._meaning_repo = meaning_repo
        self._ai_service = ai_service
        self._prompts_config = prompts_config

    def execute_follow_up(self, phrase_id: int, follow_up: MeaningFollowUp) -> None:
        """Run a follow-up action on an existing meaning."""
        check_follow_up(follow_up)
        action, text = follow_up.action, follow_up.text

        card = self._cards.card(phrase_id)
        existing = self._meaning_repo.get_by_phrase_id(phrase_id)
        current_meaning = (existing.meaning if existing else None) or ""
        current_examples = (existing.examples if existing else None) or ""

        template = _FOLLOW_UP_ACTIONS[action]
        follow_up_prompt = template.format(
            meaning=current_meaning,
            text=text or "",
        )
        combined_prompt = f"{self._user_prompt(card)}\n\n{follow_up_prompt}"

        result = self._ai_service.generate_follow_up(
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

        self._store(card, CandidateMeaning(
            candidate_id=card.word_id,
            meaning=new_meaning,
            translation=new_translation,
            synonyms=new_synonyms,
            examples=new_examples,
            ipa=new_ipa,
            generated_at=datetime.now(tz=UTC),
        ))

    def _user_prompt(self, card: GenerationCard) -> str:
        return self._prompts_config.generate_meaning_user_template.format(
            lemma=card.word.lemma,
            pos=card.word.pos,
            context=card.phrase.phrase.text,
        )

    def _store(self, card: GenerationCard, meaning: CandidateMeaning) -> None:
        """AI took a while: the phrase must still have the text the meaning explains."""
        with self._unit_of_work.write():
            if not self._occurrence_repo.holds_revision(card.phrase_id, card.phrase.revision):
                raise PhraseChangedError(card.phrase_id)
            self._meaning_repo.upsert_for_phrase(card.phrase_id, meaning)
