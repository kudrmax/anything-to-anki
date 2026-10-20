from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.application.utils.candidate_filter import CandidateFilter, keep_all
from backend.domain.entities.candidate_meaning import CandidateMeaning

if TYPE_CHECKING:
    from backend.application.utils.generation_targets import GenerationCard
    from backend.application.utils.job_phrases import JobPhrases
    from backend.domain.ports.ai_service import AIService
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.phrase_ref import PhraseRef
    from backend.domain.value_objects.prompts_config import PromptsConfig


logger = logging.getLogger(__name__)


class MeaningGenerationUseCase:
    """Generates the meanings of a batch of phrases.

    One-shot: called by worker per batch (up to 15 phrases).
    Writes each meaning to its phrase, only for phrases still wanted once AI answers and
    still at the revision their job expects. Errors (AI service unavailable) propagate:
    the worker fails the jobs.
    """

    def __init__(
        self,
        job_phrases: JobPhrases,
        meaning_repo: CandidateMeaningRepository,
        ai_service: AIService,
        prompts_config: PromptsConfig,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._job_phrases = job_phrases
        self._meaning_repo = meaning_repo
        self._ai_service = ai_service
        self._prompts_config = prompts_config
        self._unit_of_work = unit_of_work

    def execute_batch(
        self,
        phrases: list[PhraseRef],
        still_wanted: CandidateFilter = keep_all,
    ) -> list[int]:
        """Returns the wanted phrases AI gave no answer for."""
        if not phrases:
            return []

        active = [c for c in self._job_phrases.cards(phrases) if self._waits(c)]
        if not active:
            logger.info(
                "MeaningGeneration batch: all phrases skipped (status changed or done)"
            )
            return []

        user_template = self._prompts_config.generate_meaning_user_template
        parts: list[str] = [
            user_template.format(
                lemma=c.word.lemma, pos=c.word.pos, context=c.phrase.phrase.text,
            )
            for c in active
        ]
        batch_prompt = "\n\n".join(
            f"Word {i}: {part}" for i, part in enumerate(parts, 1)
        )

        results = self._ai_service.generate_meanings_batch(
            self._prompts_config.generate_meaning_system, batch_prompt
        )
        result_map = {r.word_index: r for r in results}
        wanted = still_wanted([c.phrase_id for c in active])

        now = datetime.now(tz=UTC)
        matched = 0
        unanswered: list[int] = []
        with self._unit_of_work.write():
            for i, c in enumerate(active, 1):
                if c.phrase_id not in wanted or not self._job_phrases.holds(c):
                    continue
                r = result_map.get(i)
                if r is None:
                    unanswered.append(c.phrase_id)
                    continue
                self._meaning_repo.upsert_for_phrase(c.phrase_id, CandidateMeaning(
                    candidate_id=c.word_id,
                    meaning=r.meaning,
                    translation=r.translation,
                    synonyms=r.synonyms,
                    examples=r.examples,
                    ipa=r.ipa,
                    generated_at=now,
                ))
                matched += 1

        logger.info(
            "MeaningGeneration batch: %d/%d matched, %d still wanted",
            matched, len(active), len(wanted),
        )
        return unanswered

    @staticmethod
    def _waits(card: GenerationCard) -> bool:
        """Still in play and without a meaning yet."""
        meaning = card.phrase.meaning
        return card.in_play and (meaning is None or meaning.meaning is None)
