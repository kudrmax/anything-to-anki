"""The user's order of sources in tests: a settings store, and an ordering for tests that
only need a set's sources."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from backend.application.constants import SOURCE_GROUPING_SETTING, SOURCE_SORT_SETTING
from backend.application.utils.source_ordering import SourceOrdering
from backend.domain.ports.settings_repository import SettingsRepository
from backend.domain.value_objects.source_order import SourceGrouping, SourceSort

if TYPE_CHECKING:
    from backend.application.utils.source_progress import SourceProgressReader
    from backend.application.utils.topic_generation import TopicGenerationProbe
    from backend.domain.ports.candidate_repository import CandidateRepository


class InMemorySettingsRepository(SettingsRepository):
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = dict(values or {})

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.values.get(key, default)

    def set(self, key: str, value: str) -> None:
        self.values[key] = value


def order_settings(grouping: SourceGrouping, sort: SourceSort) -> InMemorySettingsRepository:
    return InMemorySettingsRepository(
        {SOURCE_GROUPING_SETTING: grouping.value, SOURCE_SORT_SETTING: sort.value},
    )


def added_order() -> SourceOrdering:
    """One flat list, newest added first: the order of the source repository, so a test of
    a set reads no stages and no marks."""
    return SourceOrdering(
        settings_repo=order_settings(SourceGrouping.NONE, SourceSort.ADDED),
        review_progress=MagicMock(),
        generation_probe=MagicMock(),
        candidate_repo=MagicMock(),
    )


def source_ordering(
    settings_repo: SettingsRepository,
    review_progress: SourceProgressReader,
    generation_probe: TopicGenerationProbe,
    candidate_repo: CandidateRepository,
) -> SourceOrdering:
    return SourceOrdering(
        settings_repo=settings_repo,
        review_progress=review_progress,
        generation_probe=generation_probe,
        candidate_repo=candidate_repo,
    )
