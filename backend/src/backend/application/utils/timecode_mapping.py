from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.parsed_srt import ParsedSrt


def find_timecodes(
    context_fragment: str,
    parsed: ParsedSrt,
) -> tuple[int, int] | None:
    """Find the subtitle time range covering the given context fragment.

    Returns (start_ms, end_ms) from the union of all blocks that overlap
    with the fragment's character range in the cleaned text.
    Returns None if the fragment is not found or no blocks cover it.
    """
    if not parsed.blocks:
        return None

    pos = parsed.text.find(context_fragment)
    if pos == -1:
        return None

    frag_start = pos
    frag_end = pos + len(context_fragment)

    covering = [
        b for b in parsed.blocks
        if b.char_start < frag_end and b.char_end > frag_start
    ]
    if not covering:
        return None

    return min(b.start_ms for b in covering), max(b.end_ms for b in covering)
