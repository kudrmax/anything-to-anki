from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from backend.application.dto.generation_dtos import GenerationKindStatusDTO, GenerationStatusDTO
from backend.application.utils.generation_targets import CardJobs, ReadyCards
from backend.domain.services.generation_blocker import set_blocker
from backend.domain.services.generation_scope import in_scope
from backend.domain.value_objects.card_generation_state import CardGenerationState
from backend.domain.value_objects.generation_blocker import GenerationBlocker
from backend.domain.value_objects.generation_scope import GenerationScope
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.application.utils.generation_targets import (
        GenerationCard,
        GenerationCards,
        GenerationTarget,
    )
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.entities.source import Source
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.value_objects.generation_kind import GenerationKind
    from backend.domain.value_objects.source_scope import SourceScope


class GetGenerationStatusUseCase:
    """How far every kind of background generation got for the cards of a set of sources:
    the counts of each kind summed over the sources it applies to."""

    def __init__(
        self,
        scope_resolver: SourceScopeResolver,
        cards: GenerationCards,
        job_repo: JobRepository,
        candidate_sorter: CandidateSorter,
        targets: list[GenerationTarget],
    ) -> None:
        self._scope_resolver = scope_resolver
        self._cards = cards
        self._job_repo = job_repo
        self._candidate_sorter = candidate_sorter
        self._targets = targets

    def execute(self, scope: SourceScope) -> GenerationStatusDTO:
        of_sources = [
            self._of_source(source) for source in self._scope_resolver.reviewable_sources(scope)
        ]
        per_kind: dict[GenerationKind, list[GenerationKindStatusDTO]] = {
            target.kind: [] for target in self._targets
        }
        for of_source in of_sources:
            for kind in of_source.kinds:
                per_kind[kind.kind].append(kind)
        return GenerationStatusDTO(
            kinds=[_summed(kinds) for kinds in per_kind.values() if kinds],
            in_progress=any(of_source.in_progress for of_source in of_sources),
        )

    def _of_source(self, source: Source) -> GenerationStatusDTO:
        assert source.id is not None
        cards = self._cards.of_source(source.id)
        jobs = CardJobs.of(self._job_repo, cards)
        video_downloading = self._job_repo.has_active_jobs_for_source(
            source.id, frozenset({JobType.VIDEO_DOWNLOAD}),
        )
        ready = ReadyCards.of(cards, self._candidate_sorter)
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
        blocker = target.blocker(source, video_downloading)
        covered = target.cards(cards)
        state_of = {id(c): target.state(c, target.job_of(jobs, c)) for c in covered}
        states = Counter(state_of.values())
        def taken_by(scope: GenerationScope) -> int:
            return sum(
                1 for c in covered if in_scope(scope, state_of[id(c)], target.is_ready(ready, c))
            )

        return GenerationKindStatusDTO(
            kind=target.kind,
            total=states.total(),
            done=states[CardGenerationState.DONE],
            running=states[CardGenerationState.RUNNING],
            failed=states[CardGenerationState.FAILED],
            missing=states[CardGenerationState.MISSING],
            ready_missing=taken_by(GenerationScope.READY_MISSING),
            ready_all=taken_by(GenerationScope.READY_ALL),
            all=taken_by(GenerationScope.ALL),
            blocked_by=blocker,
            videos_to_download=int(blocker is GenerationBlocker.VIDEO_NOT_DOWNLOADED),
        )


def _summed(kinds: list[GenerationKindStatusDTO]) -> GenerationKindStatusDTO:
    """One kind over several sources: counts add up, the videos to download too; it is held
    back only when every source holds it back."""
    return GenerationKindStatusDTO(
        kind=kinds[0].kind,
        total=sum(k.total for k in kinds),
        done=sum(k.done for k in kinds),
        running=sum(k.running for k in kinds),
        failed=sum(k.failed for k in kinds),
        missing=sum(k.missing for k in kinds),
        ready_missing=sum(k.ready_missing for k in kinds),
        ready_all=sum(k.ready_all for k in kinds),
        all=sum(k.all for k in kinds),
        blocked_by=set_blocker([k.blocked_by for k in kinds]),
        videos_to_download=sum(k.videos_to_download for k in kinds),
    )
