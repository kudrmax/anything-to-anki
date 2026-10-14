from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.elsewhere import Elsewhere

if TYPE_CHECKING:
    from backend.application.utils.user_vocabulary import UserVocabulary


class DecidedElsewhere:
    """Whether a word still open in a source is done all the same: known, or learned via
    another source. Ask only about a word not decided in the source itself. The user's
    priority holds: unknown > known > learning."""

    def __init__(self, vocabulary: UserVocabulary) -> None:
        self._vocabulary = vocabulary

    def of(self, lemma: str) -> Elsewhere | None:
        vocabulary = self._vocabulary.snapshot()
        if vocabulary.is_known(lemma):
            return Elsewhere.KNOWN
        if vocabulary.is_learning(lemma):
            return Elsewhere.LEARNING
        return None
