"""A real ``UserVocabulary`` over mocked word lists.

Tests keep asserting on the known-word repository mock they pass; the unknown
words and the learning words are the given lemmas.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from backend.application.utils.knowledge_scope import KnowledgeScope
from backend.application.utils.user_vocabulary import UserVocabulary

from tests.decision_support import FixedClock

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime

    from backend.domain.ports.learning_query import LearningQuery


def user_vocabulary(
    known_word_repo: MagicMock | None = None,
    unknown_lemmas: Iterable[str] = (),
    *,
    learning_lemmas: Iterable[str] = (),
    learning_query: LearningQuery | None = None,
    active_since: Mapping[str, tuple[datetime, ...]] | None = None,
) -> UserVocabulary:
    """`learning_query`: a real query in place of the given learning lemmas, which are
    Learn words waiting for export; `active_since`: when each lemma's notes in Anki were
    exported."""
    known = known_word_repo if known_word_repo is not None else MagicMock()
    if isinstance(known.get_all_pairs.return_value, MagicMock):
        known.get_all_pairs.return_value = set()
    unknown = MagicMock()
    unknown.lemmas.return_value = set(unknown_lemmas)
    learning: LearningQuery | MagicMock
    if learning_query is not None:
        learning = learning_query
    else:
        learning = MagicMock()
        learning.awaiting_export.return_value = frozenset(learning_lemmas)
        learning.active_since.return_value = dict(active_since or {})
    return UserVocabulary(known, unknown, KnowledgeScope(FixedClock(), known, unknown, learning))
