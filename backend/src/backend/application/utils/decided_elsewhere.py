from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.elsewhere import Elsewhere

if TYPE_CHECKING:
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.learning_query import LearningQuery


class DecidedElsewhere:
    """Whether a word still open in a source is done all the same: known, or learned via
    another source. Ask only about a word not decided in the source itself."""

    def __init__(self, vocabulary: UserVocabulary, learning: LearningQuery) -> None:
        self._vocabulary = vocabulary
        self._learning = learning

    def of(self, lemma: str) -> Elsewhere | None:
        if self._vocabulary.is_known(lemma):
            return Elsewhere.KNOWN
        if lemma.lower() in self._learning.learning_lemmas():
            return Elsewhere.LEARNING
        return None
