from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.learning_timer import known_on, timer_due

if TYPE_CHECKING:
    from datetime import datetime


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
    def is_known(self) -> bool:
        return not self.unknown and (self.known_marked or self.any_due)

    @property
    def timer_known(self) -> bool:
        return self.is_known and not self.known_marked

    @property
    def is_learning(self) -> bool:
        """In Anki, its 30 days not passed yet."""
        return not self.unknown and not self.is_known and bool(self.active_since)

    @property
    def is_learn(self) -> bool:
        """Marked Learn somewhere, waiting for export."""
        return (
            not self.unknown and not self.is_known and not self.is_learning
            and self.learn_anywhere
        )

    @property
    def timer_known_on(self) -> datetime | None:
        """When its oldest note in Anki makes it Known; None with no note in Anki."""
        return known_on(min(self.active_since)) if self.active_since else None

    @property
    def elsewhere(self) -> ElsewhereStatus | None:
        """What a card of the lemma open in a source shows of the user's other words."""
        if self.is_known:
            return ElsewhereStatus.KNOWN
        if self.is_learning:
            return ElsewhereStatus.LEARNING
        if self.is_learn:
            return ElsewhereStatus.LEARN
        return None
