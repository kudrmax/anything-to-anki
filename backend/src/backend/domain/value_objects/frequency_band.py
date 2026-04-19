from __future__ import annotations

from enum import Enum

# Band boundaries (lower bound inclusive)
_ULTRA_COMMON_MIN: float = 5.5
_COMMON_MIN: float = 4.5
_MID_MIN: float = 3.5
_LOW_MIN: float = 2.5


class FrequencyBand(Enum):
    """Discrete frequency band derived from Zipf value.

    Values are ordered so that higher value = more frequent band.
    Sorting by value descending gives frequent-to-rare order.
    """

    ULTRA_COMMON = 5  # zipf >= 5.5
    COMMON = 4        # 4.5 <= zipf < 5.5
    MID = 3           # 3.5 <= zipf < 4.5
    LOW = 2           # 2.5 <= zipf < 3.5
    RARE = 1          # zipf < 2.5

    @property
    def is_sweet_spot(self) -> bool:
        """MID band is the sweet spot for learning."""
        return self is FrequencyBand.MID

    @classmethod
    def from_zipf(cls, zipf: float) -> FrequencyBand:
        """Map a continuous Zipf value to a discrete band."""
        clamped = max(zipf, 0.0)
        if clamped >= _ULTRA_COMMON_MIN:
            return cls.ULTRA_COMMON
        if clamped >= _COMMON_MIN:
            return cls.COMMON
        if clamped >= _MID_MIN:
            return cls.MID
        if clamped >= _LOW_MIN:
            return cls.LOW
        return cls.RARE
