from __future__ import annotations

from dataclasses import dataclass

OFF_KEY = "off"


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
        return self.zipf is not None and zipf >= self.zipf

    @classmethod
    def from_key(cls, key: str) -> FrequentWordThreshold:
        for threshold in FREQUENT_WORD_THRESHOLDS:
            if threshold.key == key:
                return threshold
        raise ValueError(f"Unknown frequent word threshold: {key!r}")


FREQUENT_WORD_THRESHOLDS: tuple[FrequentWordThreshold, ...] = (
    FrequentWordThreshold("4.0", 4.0, ("naked", "divorce", "awkward", "hilarious")),
    FrequentWordThreshold("4.5", 4.5, ("concept", "classic", "assume", "weird")),
    FrequentWordThreshold("5.0", 5.0, ("career", "issue", "available", "figure out")),
    FrequentWordThreshold("5.5", 5.5, ("end up", "find out", "come in", "get out")),
    FrequentWordThreshold(OFF_KEY, None, ()),
)

DEFAULT_FREQUENT_WORD_THRESHOLD = FrequentWordThreshold.from_key("4.5")
