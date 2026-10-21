from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.generation_dtos import GenerationKindStatusDTO, GenerationStatusDTO
from backend.application.utils.live_generation_status import summed
from backend.domain.services.card_view import wants_ready_generation
from backend.domain.services.generation_scope import generation_counts
from backend.domain.value_objects.generation_blocker import GenerationBlocker
from backend.domain.value_objects.generation_tally import EMPTY_GENERATION_TALLY
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.application.utils.generation_targets import GenerationTarget
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.entities.source import Source
    from backend.domain.ports.card_state_query import CardStateQuery
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.value_objects.by_step import SectionsByStep
    from backend.domain.value_objects.generation_kind import GenerationKind
    from backend.domain.value_objects.generation_tally import GenerationTally
    from backend.domain.value_objects.source_scope import SourceScope

_VIDEO_DOWNLOAD = frozenset({JobType.VIDEO_DOWNLOAD})


class GetGenerationStatusUseCase:
    """How far every kind of background generation got for the cards of a set of sources:
    the counts of each kind summed over the sources it applies to, read from the stored
    projection and the job queue."""

    def __init__(
        self,
        scope_resolver: SourceScopeResolver,
        card_states: CardStateQuery,
        job_repo: JobRepository,
        threshold_resolver: FrequentWordThresholdResolver,
        targets: Sequence[GenerationTarget],
    ) -> None:
        self._scope_resolver = scope_resolver
        self._card_states = card_states
        self._job_repo = job_repo
        self._threshold_resolver = threshold_resolver
        self._targets = targets

    def execute(self, scope: SourceScope) -> GenerationStatusDTO:
        sources = self._scope_resolver.reviewable_sources(scope)
        ids = [source.id for source in sources if source.id is not None]
        step = self._threshold_resolver.resolve().zipf

        def ready(sections: SectionsByStep) -> bool:
            """Of a card the tallies count: one in play."""
            return wants_ready_generation(wants_generation=True, section=sections.at(step))

        tallies = self._card_states.generation_tallies(ids, ready)
        downloading = self._job_repo.sources_with_active_jobs(ids, _VIDEO_DOWNLOAD)
        of_sources = [
            self._of_source(
                source, tallies.get(source.id, EMPTY_GENERATION_TALLY), source.id in downloading,
            )
            for source in sources if source.id is not None
        ]
        per_kind: dict[GenerationKind, list[GenerationKindStatusDTO]] = {
            target.kind: [] for target in self._targets
        }
        for of_source in of_sources:
            for kind in of_source.kinds:
                per_kind[kind.kind].append(kind)
        return GenerationStatusDTO(
            kinds=[summed(kinds) for kinds in per_kind.values() if kinds],
            in_progress=any(of_source.in_progress for of_source in of_sources),
        )

    def _of_source(
        self, source: Source, tally: GenerationTally, video_downloading: bool,
    ) -> GenerationStatusDTO:
        kinds = [
            _kind_status(target, source, tally, video_downloading)
            for target in self._targets
            if target.applies_to(source)
        ]
        return GenerationStatusDTO(
            kinds=kinds,
            in_progress=video_downloading or any(k.running > 0 for k in kinds),
        )


def _kind_status(
    target: GenerationTarget, source: Source, tally: GenerationTally, video_downloading: bool,
) -> GenerationKindStatusDTO:
    counts = generation_counts(tally.of(target.kind))
    blocker = target.blocker(source, video_downloading)
    return GenerationKindStatusDTO(
        kind=target.kind,
        total=counts.total,
        done=counts.done,
        running=counts.running,
        failed=counts.failed,
        missing=counts.missing,
        ready_missing=counts.ready_missing,
        ready_all=counts.ready_all,
        all=counts.all,
        blocked_by=blocker,
        videos_to_download=int(blocker is GenerationBlocker.VIDEO_NOT_DOWNLOADED),
    )
