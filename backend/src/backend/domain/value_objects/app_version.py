from __future__ import annotations

import re
from dataclasses import dataclass

VERSION_PATTERN = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True, order=True)
class AppVersion:
    """A release number `major.minor.patch`; versions compare numerically."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: str) -> AppVersion:
        match = VERSION_PATTERN.fullmatch(text)
        if match is None:
            raise ValueError(f"Not a version: {text!r}")
        major, minor, patch = (int(part) for part in match.groups())
        return cls(major, minor, patch)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
