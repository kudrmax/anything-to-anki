from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.elsewhere import ElsewhereStatus

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.value_objects.vocabulary import Vocabulary


class DecidedElsewhere:
    """Whether a word still open in a source is done all the same: known, or learned via
    another source. Ask only about a word not decided in the source itself. The user's
    priority holds: unknown > known > learning."""

    def __init__(self, vocabulary: UserVocabulary) -> None:
        self._vocabulary = vocabulary

    def of(self, lemma: str) -> ElsewhereStatus | None:
        return _elsewhere(self._vocabulary.snapshot(), lemma)

    def of_lemmas(self, lemmas: Iterable[str]) -> dict[str, ElsewhereStatus | None]:
        """The same for many words, reading what the user knows once."""
        vocabulary = self._vocabulary.snapshot()
        return {lemma: _elsewhere(vocabulary, lemma) for lemma in lemmas}


def _elsewhere(vocabulary: Vocabulary, lemma: str) -> ElsewhereStatus | None:
    if vocabulary.is_known(lemma):
        return ElsewhereStatus.KNOWN
    if vocabulary.is_learning(lemma):
        return ElsewhereStatus.LEARNING
    return None
