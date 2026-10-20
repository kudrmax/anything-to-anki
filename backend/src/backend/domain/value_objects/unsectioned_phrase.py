from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase


@dataclass(frozen=True)
class UnsectionedPhrase:
    """A stored phrase that has no earned section yet, with the facts of its word that
    the section is told from. `phrase` is the one the card shows."""

    id: int
    lemma: str
    pos: str
    zipf_frequency: float
    phrase: Phrase
