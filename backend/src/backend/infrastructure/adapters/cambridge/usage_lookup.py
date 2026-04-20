from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.adapters.cambridge.usage_groups import resolve_usage_group

if TYPE_CHECKING:
    from backend.infrastructure.adapters.cambridge.sqlite_reader import CambridgeSQLiteReader

_NEUTRAL = "neutral"


class CambridgeUsageLookup:
    """Usage distribution lookup based on Cambridge Dictionary SQLite data."""

    def __init__(self, reader: CambridgeSQLiteReader) -> None:
        self._reader = reader

    def get_distribution(self, lemma: str, pos_tag: str) -> UsageDistribution:
        usage_labels = self._reader.get_usage_labels(lemma, pos_tag)
        if not usage_labels:
            return UsageDistribution(None)

        group_counts: dict[str, int] = {}
        for sense_usages in usage_labels:
            group = self._resolve_group(sense_usages)
            group_counts[group] = group_counts.get(group, 0) + 1

        total = sum(group_counts.values())
        distribution = {g: count / total for g, count in group_counts.items()}
        return UsageDistribution(distribution)

    @staticmethod
    def _resolve_group(sense_usages: list[str]) -> str:
        for raw in sense_usages:
            group = resolve_usage_group(raw)
            if group is not None:
                return group
        return _NEUTRAL
