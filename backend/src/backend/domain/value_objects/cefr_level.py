from __future__ import annotations

import enum


class CEFRLevel(enum.Enum):
    """CEFR language proficiency level."""

    A1 = 1.0
    A2 = 2.0
    B1 = 3.0
    B2 = 4.0
    C1 = 5.0
    C2 = 6.0
    UNKNOWN = 7.0

    def is_learned_at(self, user_level: CEFRLevel) -> bool:
        """A word of this level is still being learned by a user at `user_level`: it is of
        that level or above. A word of no known level always is."""
        if self is CEFRLevel.UNKNOWN:
            return True
        return bool(self.value >= user_level.value)

    def easier(self) -> CEFRLevel:
        """The level just below, the one a user learning this level reads with ease; A1 for
        A1, which has none below."""
        if self in (CEFRLevel.A1, CEFRLevel.UNKNOWN):
            return self
        return CEFRLevel(self.value - 1)

    @classmethod
    def from_float(cls, value: float) -> CEFRLevel:
        """Convert a numeric CEFR value to the nearest CEFRLevel."""
        if value <= 0:
            return cls.UNKNOWN
        closest = cls.UNKNOWN
        min_diff = float("inf")
        for level in cls:
            if level is cls.UNKNOWN:
                continue
            diff = abs(level.value - value)
            if diff < min_diff:
                min_diff = diff
                closest = level
        return closest

    @classmethod
    def from_str(cls, label: str) -> CEFRLevel:
        """Parse a string like 'B1', 'C2' into a CEFRLevel."""
        label_upper = label.strip().upper()
        try:
            return cls[label_upper]
        except KeyError:
            raise ValueError(f"Invalid CEFR level: {label!r}") from None
