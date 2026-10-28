from __future__ import annotations

from dataclasses import dataclass

OFF_KEY = "off"
# Where an average learner probably knows a word.
FALLBACK_ZIPF: float = 4.5
# Every zipf a threshold can take, the last one — no threshold: frequency is ignored.
THRESHOLD_STEPS: tuple[float | None, ...] = (2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, None)


def step_index(zipf: float | None) -> int:
    """Position of the threshold `zipf` in THRESHOLD_STEPS."""
    if zipf not in THRESHOLD_STEPS:
        raise ValueError(f"Not a threshold step: {zipf!r}")
    return THRESHOLD_STEPS.index(zipf)


def is_frequent(zipf: float, step: float | None) -> bool:
    """At least as frequent as the threshold `step`; nothing is frequent without one."""
    return step is not None and zipf >= step


@dataclass(frozen=True)
class FrequentWordThreshold:
    """Zipf frequency from which a word is treated as probably known.

    Such words are not dropped — they go to the bottom of the list.
    `examples` are words that go down exactly at this threshold, i.e. the
    ones a stricter neighbour option would still keep on top.
    """

    key: str
    zipf: float | None
    examples: tuple[str, ...]

    def covers(self, zipf: float) -> bool:
        return is_frequent(zipf, self.zipf)

    @classmethod
    def from_key(cls, key: str) -> FrequentWordThreshold:
        for threshold in FREQUENT_WORD_THRESHOLDS:
            if threshold.key == key:
                return threshold
        raise ValueError(f"Unknown frequent word threshold: {key!r}")


def _manual(zipf: float, examples: tuple[str, ...]) -> FrequentWordThreshold:
    step_index(zipf)
    return FrequentWordThreshold(str(zipf), zipf, examples)


FREQUENT_WORD_THRESHOLDS: tuple[FrequentWordThreshold, ...] = (
    _manual(4.0, ("naked", "divorce", "awkward", "hilarious")),
    _manual(4.5, ("concept", "classic", "assume", "weird")),
    _manual(5.0, ("career", "issue", "available", "figure out")),
    _manual(5.5, ("end up", "find out", "come in", "get out")),
    FrequentWordThreshold(OFF_KEY, None, ()),
)

DEFAULT_FREQUENT_WORD_THRESHOLD = FrequentWordThreshold.from_key(OFF_KEY)
