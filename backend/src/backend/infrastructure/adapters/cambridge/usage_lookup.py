"""Compute UsageDistribution from Cambridge Dictionary data."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.adapters.cambridge.cefr_source import _POS_TO_CAMBRIDGE
from backend.infrastructure.adapters.cambridge.usage_groups import resolve_usage_group

if TYPE_CHECKING:
    from backend.infrastructure.adapters.cambridge.models import (
        CambridgeEntry,
        CambridgeSense,
        CambridgeWord,
    )

_NEUTRAL = "neutral"


class CambridgeUsageLookup:
    """Lookup service for usage distribution based on Cambridge Dictionary senses."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, CambridgeWord] | None = None

    @classmethod
    def from_data(cls, data: dict[str, CambridgeWord]) -> CambridgeUsageLookup:
        """Create an instance with pre-loaded data (for tests)."""
        instance = cls.__new__(cls)
        instance._path = Path()
        instance._data = data
        return instance

    def _ensure_loaded(self) -> dict[str, CambridgeWord]:
        if self._data is None:
            from backend.infrastructure.adapters.cambridge.parser import parse_cambridge_jsonl
            self._data = parse_cambridge_jsonl(self._path)
        return self._data

    def get_distribution(self, lemma: str, pos_tag: str) -> UsageDistribution:
        """Compute usage distribution for a lemma+POS from Cambridge data."""
        data = self._ensure_loaded()
        word = data.get(lemma.lower())
        if word is None:
            return UsageDistribution(None)

        cambridge_pos = _POS_TO_CAMBRIDGE.get(pos_tag)
        entries = self._filter_entries_by_pos(word.entries, cambridge_pos)
        senses = [s for e in entries for s in e.senses]

        if not senses:
            return UsageDistribution(None)

        group_counts: dict[str, int] = {}
        for sense in senses:
            group = self._sense_group(sense)
            group_counts[group] = group_counts.get(group, 0) + 1

        total = sum(group_counts.values())
        distribution = {g: count / total for g, count in group_counts.items()}
        return UsageDistribution(distribution)

    @staticmethod
    def _sense_group(sense: CambridgeSense) -> str:
        """Determine usage group for a sense. First recognized label wins."""
        for raw in sense.usages:
            group = resolve_usage_group(raw)
            if group is not None:
                return group
        return _NEUTRAL

    @staticmethod
    def _filter_entries_by_pos(
        entries: list[CambridgeEntry],
        cambridge_pos: str | None,
    ) -> list[CambridgeEntry]:
        """Filter entries by POS. Falls back to all entries if no match."""
        if cambridge_pos is None:
            return list(entries)
        matched = [e for e in entries if cambridge_pos in e.pos]
        return matched if matched else list(entries)
