from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.application.utils.candidate_filter import CandidateFilter, keep_all
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.ports.ai_service import AIService
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.value_objects.prompts_config import PromptsConfig


logger = logging.getLogger(__name__)


class MeaningGenerationUseCase:
    """Generates meanings for a batch of candidates.

    One-shot: called by worker per batch (up to 15 candidates).
    Writes results to candidate_meanings, only for candidates still wanted once
    AI answers. Errors (AI service unavailable) propagate: the worker fails the jobs.
    """

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

    def execute_batch(
        self,
        candidate_ids: list[int],
        still_wanted: CandidateFilter = keep_all,
    ) -> list[int]:
        """Returns the wanted candidates AI gave no answer for."""
        if not candidate_ids:
            return []

        candidates = self._candidate_repo.get_by_ids(candidate_ids)
        # Filter out candidates whose status changed (KNOWN/SKIP) or already have meaning
        active = [
            c for c in candidates
            if (c.meaning is None or c.meaning.meaning is None)
            and c.status in (CandidateStatus.PENDING, CandidateStatus.LEARN)
        ]

        if not active:
            logger.info(
                "MeaningGeneration batch: all candidates skipped (status changed or done)"
            )
            return []

        user_template = self._prompts_config.generate_meaning_user_template
        parts: list[str] = [
            user_template.format(
                lemma=c.lemma, pos=c.pos, context=c.card_phrase
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
        wanted = still_wanted([c.id for c in active if c.id is not None])

        now = datetime.now(tz=UTC)
        matched = 0
        unanswered: list[int] = []
        for i, c in enumerate(active, 1):
            if c.id is None or c.id not in wanted:
                continue
            r = result_map.get(i)
            if r is None:
                unanswered.append(c.id)
                continue
            self._meaning_repo.upsert(CandidateMeaning(
                candidate_id=c.id,
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
