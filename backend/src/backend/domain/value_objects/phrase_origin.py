from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PhraseOriginKind(StrEnum):
    """Where the context phrase of a candidate came from."""

    SOURCE = "source"
    GENERATED = "generated"


@dataclass(frozen=True)
class PhraseOrigin:
    """Origin of a phrase borrowed from outside the candidate's own source.

    Regular candidates have no origin: their phrase comes from their source.
    """

    kind: PhraseOriginKind
    source_title: str | None = None

    @classmethod
    def from_source(cls, source_title: str) -> PhraseOrigin:
        return cls(kind=PhraseOriginKind.SOURCE, source_title=source_title)

    @classmethod
    def generated(cls) -> PhraseOrigin:
        return cls(kind=PhraseOriginKind.GENERATED)
