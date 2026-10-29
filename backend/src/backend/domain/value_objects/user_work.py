from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserWork:
    """What the user made of a card besides its choice: an edit of its phrase, the phrase
    picked for the card, a phrase added that the analysis did not cut, or the card removed."""

    edited: bool = False
    picked: bool = False
    added: bool = False
    removed: bool = False

    @property
    def any(self) -> bool:
        return self.edited or self.picked or self.added or self.removed


NO_USER_WORK = UserWork()
