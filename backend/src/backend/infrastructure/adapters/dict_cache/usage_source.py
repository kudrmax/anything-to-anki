"""UsageSource backed by the unified dictionary cache."""
from __future__ import annotations

from backend.domain.ports.usage_source import UsageSource
from backend.domain.services.pos_mapping import map_pos_tag
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader


class DictCacheUsageSource(UsageSource):
    def __init__(self, reader: DictCacheReader) -> None:
        self._reader = reader

    def get_distribution(self, lemma: str, pos_tag: str) -> UsageDistribution:
        unified_pos = map_pos_tag(pos_tag) or pos_tag
        labels = self._reader.get_usage_labels(lemma, unified_pos)
        if labels is None or not labels:
            return UsageDistribution(None)
        weight = 1.0 / len(labels)
        groups = {label: weight for label in labels}
        return UsageDistribution(groups)
