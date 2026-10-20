from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.learning_timer import known_on, timer_due

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime


_BOTH = (False, True)
STANDING: Mapping[tuple[bool, bool, bool], ElsewhereStatus | None] = MappingProxyType({
    **{(True, in_anki, waiting): ElsewhereStatus.KNOWN
       for in_anki, waiting in product(_BOTH, _BOTH)},
    **{(False, True, waiting): ElsewhereStatus.LEARNING for waiting in _BOTH},
    (False, False, True): ElsewhereStatus.LEARN,
    (False, False, False): None,
})
"""(Known, in Anki, Learn waiting for export) → what the lemma stands as: Known beats
Learning, and Learning beats Learn (Q12)."""


@dataclass(frozen=True)
class LemmaKnowledge:
    """What the user's lists and Anki bindings say about one lemma at one moment."""

    known_marked: bool
    unknown: bool
    learn_anywhere: bool
    active_since: tuple[datetime, ...]
    any_due: bool

    @classmethod
    def at(
        cls, now: datetime, *, known_marked: bool, unknown: bool, learn_anywhere: bool,
        active_since: tuple[datetime, ...],
    ) -> LemmaKnowledge:
        return cls(
            known_marked=known_marked, unknown=unknown, learn_anywhere=learn_anywhere,
            active_since=active_since,
            any_due=any(timer_due(since, now) for since in active_since),
        )

    @property
    def listed_known(self) -> bool:
        """In the Known list, and not in Unknown too."""
        # Stage 4 migration removes pre-existing conflicts
        return self.known_marked and not self.unknown

    @property
    def is_known(self) -> bool:
        return self.listed_known or self.any_due

    @property
    def timer_known(self) -> bool:
        return self.is_known and not self.listed_known

    @property
    def is_learning(self) -> bool:
        """In Anki, its 30 days not passed yet."""
        return self.elsewhere is ElsewhereStatus.LEARNING

    @property
    def is_learn(self) -> bool:
        """Marked Learn somewhere, waiting for export."""
        return self.elsewhere is ElsewhereStatus.LEARN

    @property
    def timer_known_on(self) -> datetime | None:
        """When its oldest note in Anki makes it Known; None with no note in Anki."""
        return known_on(min(self.active_since)) if self.active_since else None

    @property
    def elsewhere(self) -> ElsewhereStatus | None:
        """What a card of the lemma open in a source shows of the user's other words."""
        return STANDING[(self.is_known, bool(self.active_since), self.learn_anywhere)]
