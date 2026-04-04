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

    def is_above(self, user_level: CEFRLevel) -> bool:
        """Check if this level is strictly above the given user level."""
        if self is CEFRLevel.UNKNOWN:
            return True
        return bool(self.value > user_level.value)

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
