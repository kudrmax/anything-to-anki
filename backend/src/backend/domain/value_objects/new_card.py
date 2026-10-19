from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin import PhraseOrigin


@dataclass(frozen=True)
class NewCard:
    """A word read from a phrase someone picked, and that phrase, before either is stored.

    `origin`: where a collected phrase came from — another source, or AI made it.
    `position`: the phrase's place in the source's document, when it has one.
    """

    word: StoredCandidate
    phrase: Phrase
    origin: PhraseOrigin | None = None
    position: DocumentPosition | None = None
