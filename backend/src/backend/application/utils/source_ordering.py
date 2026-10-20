from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import SOURCE_GROUPING_SETTING, SOURCE_SORT_SETTING
from backend.domain.services.source_order import SourceFacts, arrange
from backend.domain.services.source_stage import source_stage
from backend.domain.value_objects.source_order import (
    DEFAULT_SOURCE_GROUPING,
    DEFAULT_SOURCE_SORT,
    SourceGrouping,
    SourceOrder,
    SourceSort,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime

    from backend.application.utils.review_progress import ReviewProgress
    from backend.application.utils.topic_generation import TopicGenerationProbe
    from backend.domain.entities.source import Source
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.services.source_order import SourceGroup
    from backend.domain.value_objects.source_stage import SourceStage


class SourceOrdering:
    """Puts sources in the user's order (`source_order.arrange`), reading only the facts
    that order needs: the stages when grouped by stage, the last marks when sorted by them.
    """

    def __init__(
        self,
        settings_repo: SettingsRepository,
        review_progress: ReviewProgress,
        generation_probe: TopicGenerationProbe,
        candidate_repo: CandidateRepository,
    ) -> None:
        self._settings = settings_repo
        self._review_progress = review_progress
        self._generation_probe = generation_probe
        self._candidates = candidate_repo

    def order(self) -> SourceOrder:
        return SourceOrder(
            grouping=SourceGrouping(
                self._settings.get(SOURCE_GROUPING_SETTING) or DEFAULT_SOURCE_GROUPING,
            ),
            sort=SourceSort(self._settings.get(SOURCE_SORT_SETTING) or DEFAULT_SOURCE_SORT),
        )

    def arrange(
        self, sources: Sequence[Source], stages: Mapping[int, SourceStage] | None = None,
    ) -> list[SourceGroup]:
        """`stages`: the stages of the sources when the caller has read them already."""
        order = self.order()
        listed = [s for s in sources if s.id is not None]
        if order.grouping is SourceGrouping.NONE:
            stages = {}
        elif stages is None:
            stages = self._stages(listed)
        studied = self._last_studied(listed) if order.sort is SourceSort.LAST_STUDIED else {}
        return arrange(
            [SourceFacts(s, stages.get(_id(s)), studied.get(_id(s))) for s in listed], order,
        )

    def _stages(self, sources: list[Source]) -> dict[int, SourceStage]:
        progress = self._review_progress.of_sources([_id(s) for s in sources])
        return {
            _id(s): source_stage(
                s.status, progress[_id(s)],
                awaiting_generation=self._generation_probe.of(s).awaiting,
            )
            for s in sources
        }

    def _last_studied(self, sources: list[Source]) -> dict[int, datetime]:
        return self._candidates.last_studied([_id(s) for s in sources])


def _id(source: Source) -> int:
    assert source.id is not None
    return source.id
