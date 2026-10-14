from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase


@dataclass(frozen=True)
class ShownPlace:
    """Where a shown phrase stands in its source's document, for marking its target."""

    phrase_id: int
    word_id: int
    cefr_level: str | None
    is_phrasal_verb: bool
    source_phrase: Phrase
    position: DocumentPosition
