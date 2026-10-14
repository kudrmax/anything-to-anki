"""A real ``UserVocabulary`` over mocked word lists.

Tests keep asserting on the known-word repository mock they pass; the unknown
words and the learning words are the given lemmas.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from backend.application.utils.user_vocabulary import UserVocabulary

if TYPE_CHECKING:
    from collections.abc import Iterable


def user_vocabulary(
    known_word_repo: MagicMock | None = None,
    unknown_lemmas: Iterable[str] = (),
    *,
    learning_lemmas: Iterable[str] = (),
    removals: MagicMock | None = None,
) -> UserVocabulary:
    known = known_word_repo if known_word_repo is not None else MagicMock()
    if isinstance(known.get_all_pairs.return_value, MagicMock):
        known.get_all_pairs.return_value = set()
    unknown = MagicMock()
    unknown.lemmas.return_value = set(unknown_lemmas)
    learning = MagicMock()
    learning.learning_lemmas.return_value = frozenset(learning_lemmas)
    if removals is None:
        removals = MagicMock()
        removals.contains.return_value = False
    return UserVocabulary(known, unknown, learning, removals)
