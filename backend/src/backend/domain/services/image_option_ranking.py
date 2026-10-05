from __future__ import annotations

from itertools import chain, zip_longest
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.value_objects.image_option import ImageOption


def rank_image_options(found_per_source: Sequence[Sequence[ImageOption]]) -> list[ImageOption]:
    """Order pictures for the user to pick from.

    Dictionary pictures go first: they show exactly the word. Search engines
    follow in turns — one picture from each before the next round — so the
    best guesses of every engine are on top. A picture offered twice is kept
    only where it first appears.
    """
    dictionary = [o for found in found_per_source for o in found if o.provider.is_dictionary]
    searched = [[o for o in found if not o.provider.is_dictionary] for found in found_per_source]
    in_turns = (o for o in chain.from_iterable(zip_longest(*searched)) if o is not None)

    ranked: list[ImageOption] = []
    seen_urls: set[str] = set()
    for option in chain(dictionary, in_turns):
        if option.url not in seen_urls:
            seen_urls.add(option.url)
            ranked.append(option)
    return ranked
