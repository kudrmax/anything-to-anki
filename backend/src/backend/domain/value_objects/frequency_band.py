from __future__ import annotations

from dataclasses import dataclass

SWEET_SPOT_MIN: float = 3.0
SWEET_SPOT_MAX: float = 4.5


@dataclass(frozen=True, order=True)
class FrequencyBand:
    """Word frequency represented as a Zipf value.

    Higher zipf_value = more frequent word = less useful to learn.
    Sorting: ascending by zipf_value puts rare (more useful) words first.
    """

    zipf_value: float

    @property
    def is_sweet_spot(self) -> bool:
        """Zipf 3.0–4.5 zone — most rewarding words to learn (approx K3000–K9000)."""
        return SWEET_SPOT_MIN <= self.zipf_value <= SWEET_SPOT_MAX

    @classmethod
    def from_zipf(cls, zipf: float) -> FrequencyBand:
        return cls(zipf_value=max(zipf, 0.0))
