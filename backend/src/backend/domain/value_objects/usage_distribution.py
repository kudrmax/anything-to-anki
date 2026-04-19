"""Usage distribution value object."""
from __future__ import annotations

from dataclasses import dataclass

_NEUTRAL = "neutral"


@dataclass(frozen=True)
class UsageDistribution:
    """Distribution of Cambridge usage groups across a word's senses.

    None means the word was not found in Cambridge.
    Empty dict is treated the same as None (neutral).
    """

    groups: dict[str, float] | None

    def primary_group(self, order: list[str]) -> str:
        """Return the highest-priority group present in this distribution.

        Priority is determined by position in `order` (index 0 = highest).
        Returns 'neutral' if distribution is None/empty or no groups match.
        """
        if not self.groups:
            return _NEUTRAL
        for group in order:
            if group in self.groups:
                return group
        return _NEUTRAL

    def rank(self, order: list[str]) -> int:
        """Return the sort rank (index in order) of the primary group.

        Lower rank = higher priority in sorting.
        """
        group = self.primary_group(order)
        try:
            return order.index(group)
        except ValueError:
            return len(order)

    def to_dict(self) -> dict[str, float] | None:
        """Serialize for storage."""
        return dict(self.groups) if self.groups else None
