from __future__ import annotations

from dataclasses import dataclass

SURROUNDING_CHARS = 300


@dataclass(frozen=True)
class FragmentSurroundings:
    """Source text right before and after a card's phrase — to see what the
    phrase boundary cut off."""

    before: str
    after: str

    @classmethod
    def find(
        cls, text: str, fragment: str, width: int = SURROUNDING_CHARS,
    ) -> FragmentSurroundings | None:
        """None when the phrase is not in the text (edited by hand, borrowed)."""
        start = text.find(fragment) if fragment else -1
        if start < 0:
            return None
        end = start + len(fragment)
        return cls(before=text[max(0, start - width):start], after=text[end:end + width])
