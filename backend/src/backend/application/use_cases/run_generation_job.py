from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Callable

from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.domain.value_objects.generation_job_status import GenerationJobStatus

if TYPE_CHECKING:
    from backend.domain.ports.ai_service import AIService
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.generation_job_repository import GenerationJobRepository
    from backend.domain.ports.prompt_repository import PromptRepository

_GENERATE_MEANING_KEY = "generate_meaning"
logger = logging.getLogger(__name__)


class RunGenerationJobUseCase:
    """Executes a generation job: processes one batch of candidates via AI.

    One job = one batch (up to 15 candidates).
    """

    def __init__(
        self,
        job_repo: GenerationJobRepository,
        candidate_repo: CandidateRepository,
        meaning_repo: CandidateMeaningRepository,
        ai_service: AIService,
        prompt_repo: PromptRepository,
    ) -> None:
        self._job_repo = job_repo
        self._candidate_repo = candidate_repo
        self._meaning_repo = meaning_repo
        self._ai_service = ai_service
        self._prompt_repo = prompt_repo

    def execute(self, job_id: int, commit: Callable[[], None]) -> None:
        job = self._job_repo.get_by_id(job_id)
        if job is None:
            return

        # Check if job was cancelled before execution
        if job.status in (GenerationJobStatus.CANCELLED, GenerationJobStatus.PAUSED):
            return

        job.status = GenerationJobStatus.RUNNING
        self._job_repo.update(job)
        commit()
        logger.info("Generation job %d: RUNNING, batch_size=%d", job_id, job.total_candidates)

        prompt = self._prompt_repo.get_by_key(_GENERATE_MEANING_KEY)
        if prompt is None:
            job.status = GenerationJobStatus.FAILED
            self._job_repo.update(job)
            commit()
            return

        try:
            self._process_batch(job, prompt, commit)
        except Exception:
            logger.exception("Generation job %d crashed", job_id)
            job = self._job_repo.get_by_id(job_id)
            if job is not None:
                job.status = GenerationJobStatus.FAILED
                self._job_repo.update(job)
                commit()

    def _process_batch(
        self,
        job: object,
        prompt: object,
        commit: Callable[[], None],
    ) -> None:
        from backend.domain.entities.generation_job import GenerationJob
        from backend.domain.entities.prompt_template import PromptTemplate

        assert isinstance(job, GenerationJob)  # noqa: S101
        assert isinstance(prompt, PromptTemplate)  # noqa: S101

        # Get candidates by explicit IDs
        candidates = self._candidate_repo.get_by_ids(job.candidate_ids)

        # Filter: only process those still PENDING/LEARN and without meaning
        active = [
            c for c in candidates
            if (c.meaning is None or c.meaning.meaning is None)
            and c.status in (CandidateStatus.PENDING, CandidateStatus.LEARN)
        ]
        skipped = len(candidates) - len(active)

        if not active:
            # All candidates skipped (became KNOWN/SKIP) — complete successfully
            job.status = GenerationJobStatus.COMPLETED
            job.skipped_candidates = skipped
            self._job_repo.update(job)
            commit()
            logger.info("Generation job %d: all candidates skipped (status changed)", job.id)
            return

        # Format batch user prompt
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

        try:
            results = self._ai_service.generate_meanings_batch(
                prompt.system_prompt, batch_prompt
            )
            # Match results back to candidates by word_index (1-based position in batch)
            result_map = {r.word_index: r for r in results}
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
                        generated_at=datetime.now(tz=UTC),
                    ))
                    matched += 1
            job.processed_candidates = matched
            job.failed_candidates = len(active) - matched
            job.skipped_candidates = skipped
            job.status = GenerationJobStatus.COMPLETED
            logger.info(
                "Generation job %d: COMPLETED, processed=%d, failed=%d, skipped=%d",
                job.id, matched, len(active) - matched, skipped
            )
        except Exception:
            logger.exception("Batch generation failed for job %d", job.id)
            job.failed_candidates = len(active)
            job.skipped_candidates = skipped
            job.status = GenerationJobStatus.FAILED

        self._job_repo.update(job)
        commit()
