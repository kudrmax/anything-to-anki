from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionProgress:
    """How many of the cards that count the user is done with."""

    decided: int = 0
    total: int = 0

    def __add__(self, other: DecisionProgress) -> DecisionProgress:
        return DecisionProgress(
            decided=self.decided + other.decided, total=self.total + other.total,
        )
