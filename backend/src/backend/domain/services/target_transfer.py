from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase


def target_in(source: Phrase, shown: Phrase) -> tuple[int, ...] | None:
    """The target of `shown`, a rewrite of `source`, as words of `source`: the same
    dictionary forms in the same order, each the first one after the one before.
    None when `source` lacks one of them."""
    if shown.text == source.text:
        return shown.target
    found: list[int] = []
    start = 0
    for index in shown.target:
        lemma = shown.words[index].lemma.lower()
        match = next(
            (i for i in range(start, len(source.words)) if source.words[i].lemma.lower() == lemma),
            None,
        )
        if match is None:
            return None
        found.append(match)
        start = match + 1
    return tuple(found)
