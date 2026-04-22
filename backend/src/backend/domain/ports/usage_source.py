from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.value_objects.usage_distribution import UsageDistribution


class UsageSource(ABC):
    """Port for looking up usage labels by lemma and POS."""

    @abstractmethod
    def get_distribution(self, lemma: str, pos_tag: str) -> UsageDistribution:
        """Return usage distribution for the given word.

        Returns UsageDistribution(None) if the word is not found.
        """
