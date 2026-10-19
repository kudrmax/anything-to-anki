from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from backend.application.dto.generation_dtos import GenerationKindStatusDTO, GenerationStatusDTO
from backend.application.utils.generation_targets import CardJobs, ReadyCards
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.services.generation_scope import in_scope
from backend.domain.value_objects.card_generation_state import CardGenerationState
from backend.domain.value_objects.generation_scope import GenerationScope
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.application.utils.generation_targets import (
        GenerationCard,
        GenerationCards,
        GenerationTarget,
    )
    from backend.domain.entities.source import Source
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository


class GetGenerationStatusUseCase:
    """How far every kind of background generation got for a source's cards."""

    def __init__(
        self,
        source_repo: SourceRepository,
        cards: GenerationCards,
        job_repo: JobRepository,
        targets: list[GenerationTarget],
    ) -> None:
        self._source_repo = source_repo
        self._cards = cards
        self._job_repo = job_repo
        self._targets = targets

    def execute(self, source_id: int) -> GenerationStatusDTO:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        cards = self._cards.of_source(source_id)
        jobs = CardJobs.of(self._job_repo, cards)
        video_downloading = self._job_repo.has_active_jobs_for_source(
            source_id, frozenset({JobType.VIDEO_DOWNLOAD}),
        )
        ready = ReadyCards.of(cards)
        kinds = [
            self._kind_status(target, source, cards, jobs, ready, video_downloading)
            for target in self._targets
            if target.applies_to(source)
        ]
        return GenerationStatusDTO(
            kinds=kinds,
            in_progress=video_downloading or any(k.running > 0 for k in kinds),
        )

    @staticmethod
    def _kind_status(
        target: GenerationTarget,
        source: Source,
        cards: list[GenerationCard],
        jobs: CardJobs,
        ready: ReadyCards,
        video_downloading: bool,
    ) -> GenerationKindStatusDTO:
        covered = target.cards(cards)
        state_of = {id(c): target.state(c, target.job_of(jobs, c)) for c in covered}
        states = Counter(state_of.values())
        ready_missing = sum(
            1 for c in covered
            if in_scope(GenerationScope.READY_MISSING, state_of[id(c)], target.is_ready(ready, c))
        )
        return GenerationKindStatusDTO(
            kind=target.kind,
            total=states.total(),
            done=states[CardGenerationState.DONE],
            running=states[CardGenerationState.RUNNING],
            failed=states[CardGenerationState.FAILED],
            missing=states[CardGenerationState.MISSING],
            ready_missing=ready_missing,
            blocked_by=target.blocker(source, video_downloading),
        )
