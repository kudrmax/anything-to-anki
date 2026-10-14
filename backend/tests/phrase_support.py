"""Card phrases for tests, without a parser.

Every word is its own lowercase lemma, easy and frequent, so no word of a phrase is new
unless a test says which are (`new`). The target is the given words in order — by
dictionary form or as written — or the first word.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.phrase_building import (
    TokenFacts,
    target_by_lemma,
    word_spans,
    words_of,
)
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.phrase import Phrase

if TYPE_CHECKING:
    from collections.abc import Iterable

EASY_ZIPF = 6.0
RARE_ZIPF = 2.5


def phrase(
    text: str,
    target: str | None = None,
    *,
    new: Iterable[str] = (),
    lemmas: dict[str, str] | None = None,
) -> Phrase:
    """`new`: words that are rare and above any level; `lemmas`: word → its dictionary form."""
    rare = {word.lower() for word in new}
    forms = {k.lower(): v for k, v in (lemmas or {}).items()}
    facts = [
        TokenFacts(
            start=start, end=end,
            lemma=forms.get(text[start:end].lower(), text[start:end].lower()),
            level=CEFRLevel.C2 if text[start:end].lower() in rare else CEFRLevel.A1,
            zipf=RARE_ZIPF if text[start:end].lower() in rare else EASY_ZIPF,
            content=text[start:end].lower() in rare,
            alpha=True,
        )
        for start, end in word_spans(text)
    ]
    words = words_of(text, facts)
    found = target_by_lemma(words, text, target) if target else ()
    return Phrase(text=text, words=words, target=found or (0,))
