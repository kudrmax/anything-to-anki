from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind


@dataclass(frozen=True)
class CandidateCloze:
    """The user's cloze markup for a candidate (1:1): which words of the phrase are hidden.

    `phrase` is the card phrase the indices point into; once the card phrase
    changes the markup is rebuilt (see ClozeBuilder.effective).
    """

    candidate_id: int
    hidden_word_indices: tuple[int, ...]
    hint_kind: ClozeHintKind
    custom_hint: str | None
    phrase: str
