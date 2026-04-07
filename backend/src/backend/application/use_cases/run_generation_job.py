from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.exceptions import InvalidPromptError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus

if TYPE_CHECKING:
    from backend.domain.ports.ai_service import AIService
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.prompt_repository import PromptRepository

_GENERATE_MEANING_KEY = "generate_meaning"
logger = logging.getLogger(__name__)


class MeaningGenerationUseCase:
    """Generates meanings for a batch of candidates.

    One-shot: called by worker per batch (up to 15 candidates).
    Writes status transitions (RUNNING → DONE) to candidate_meanings.
    Permanent errors (missing prompt) raise PermanentAIError subclasses.
    Transient errors (AI service unavailable) propagate for ARQ retry.
    """

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

    def execute_batch(self, candidate_ids: list[int]) -> None:
        if not candidate_ids:
            return

        # Mark all RUNNING upfront
        for cid in candidate_ids:
            self._meaning_repo.mark_running(cid)

        prompt = self._prompt_repo.get_by_key(_GENERATE_MEANING_KEY)
        if prompt is None:
            raise InvalidPromptError(f"Prompt '{_GENERATE_MEANING_KEY}' not found")

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
            return

        # Format batch prompt
        parts: list[str] = []
        for c in active:
            parts.append(
                prompt.user_template.format(
                    lemma=c.lemma, pos=c.pos, context=c.context_fragment
                )
            )
        batch_prompt = "\n\n".join(
            f"Word {i}: {part}" for i, part in enumerate(parts, 1)
        )

        # Transient errors propagate → ARQ retries
        results = self._ai_service.generate_meanings_batch(
            prompt.system_prompt, batch_prompt
        )
        result_map = {r.word_index: r for r in results}

        now = datetime.now(tz=UTC)
        matched = 0
        for i, c in enumerate(active, 1):
            r = result_map.get(i)
            if r is not None and c.id is not None:
                self._meaning_repo.upsert(CandidateMeaning(
                    candidate_id=c.id,
                    meaning=r.meaning,
                    ipa=r.ipa,
                    status=EnrichmentStatus.DONE,
                    error=None,
                    generated_at=now,
                ))
                matched += 1

        logger.info(
            "MeaningGeneration batch: %d/%d matched",
            matched, len(active),
        )
