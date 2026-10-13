from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.services.document_layout import DocumentLayout

if TYPE_CHECKING:
    from backend.domain.value_objects.document import Document
    from backend.domain.value_objects.document_position import DocumentPosition

SURROUNDING_CHARS = 300


@dataclass(frozen=True)
class FragmentSurroundings:
    """Text of the document right before and after a card's phrase, as the source
    screen shows it — to see what the phrase boundary cut off."""

    before: str
    after: str

    @classmethod
    def around(
        cls,
        document: Document | None,
        position: DocumentPosition | None,
        width: int = SURROUNDING_CHARS,
    ) -> FragmentSurroundings | None:
        """None when the phrase has no place in a document (an example, a borrowed phrase)."""
        if document is None or position is None:
            return None
        layout = DocumentLayout(document)
        start, end = layout.span(position)
        text = layout.text
        return cls(before=text[max(0, start - width):start], after=text[end:end + width])
