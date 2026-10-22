from __future__ import annotations

# From the cut a parse loses least to the cut it loses most: a sentence never crosses a
# blank line, a line break most often ends one, a space only ends a word.
SEPARATORS = ("\n\n", "\n", " ")


def text_pieces(text: str, limit: int) -> list[tuple[int, int]]:
    """Cuts the text into pieces of at most `limit` characters, as (start, end).

    A piece ends at the latest blank line that fits, failing that at a line break, then at
    a space, and a word longer than the limit is cut where it reaches it. The whitespace
    around a cut stays with the piece before it, so the next piece starts at a word.
    """
    pieces: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        end = len(text) if len(text) - start <= limit else _cut(text, start, start + limit)
        pieces.append((start, end))
        start = end
    return pieces


def _cut(text: str, start: int, stop: int) -> int:
    for separator in SEPARATORS:
        found = text.rfind(separator, start, stop)
        while found >= start:
            run_start, run_end = _whitespace_run(text, found)
            if start < run_end <= stop:
                return run_end
            found = text.rfind(separator, start, run_start)
    return stop


def _whitespace_run(text: str, inside: int) -> tuple[int, int]:
    run_start = inside
    while run_start > 0 and text[run_start - 1].isspace():
        run_start -= 1
    run_end = inside
    while run_end < len(text) and text[run_end].isspace():
        run_end += 1
    return run_start, run_end
