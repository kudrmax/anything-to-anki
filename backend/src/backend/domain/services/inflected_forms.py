from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

# Suffix of an inflected form → the endings its base may have instead.
_SUFFIX_BASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ies", ("y",)),
    ("ied", ("y",)),
    ("ing", ("", "e")),
    ("es", ("",)),
    ("ed", ("", "e")),
    ("en", ("", "e")),
    ("s", ("",)),
    ("n", ("",)),
)
_DOUBLED_SUFFIXES: tuple[str, ...] = ("ing", "ed")
_MIN_BASE_LENGTH = 2


def _bases(form: str) -> Iterator[str]:
    for suffix, endings in _SUFFIX_BASES:
        if not form.endswith(suffix):
            continue
        stem = form[: -len(suffix)]
        for ending in endings:
            yield stem + ending
        if suffix in _DOUBLED_SUFFIXES and len(stem) > 1 and stem[-1] == stem[-2]:
            yield stem[:-1]


def is_inflected_form(lemma: str, lemmas: set[str]) -> bool:
    """`lemma` is a plural, -ing, past or participle form of another word of `lemmas`:
    `playing` of `play`, `known` of `know`. Texts lemmatize such a form to its base."""
    return any(
        len(base) >= _MIN_BASE_LENGTH and base != lemma and base in lemmas
        for base in _bases(lemma)
    )
