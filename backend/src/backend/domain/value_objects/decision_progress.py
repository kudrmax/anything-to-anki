from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@dataclass(frozen=True)
class DecisionProgress:
    """How many candidates the user has already decided on: any status but pending."""

    decided: int = 0
    total: int = 0

    @classmethod
    def of_counts(cls, counts: Mapping[CandidateStatus, int]) -> DecisionProgress:
        total = sum(counts.values())
        return cls(decided=total - counts.get(CandidateStatus.PENDING, 0), total=total)

    @classmethod
    def of_statuses(cls, statuses: Iterable[CandidateStatus]) -> DecisionProgress:
        return cls.of_counts(Counter(statuses))

    def __add__(self, other: DecisionProgress) -> DecisionProgress:
        return DecisionProgress(
            decided=self.decided + other.decided, total=self.total + other.total,
        )
