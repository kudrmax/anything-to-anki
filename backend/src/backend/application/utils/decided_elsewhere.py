from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.value_objects.elsewhere import ElsewhereStatus


class DecidedElsewhere:
    """Whether a word still open in a source is done all the same: known, in Anki, or marked
    Learn via another source (LemmaKnowledge.elsewhere), read from the request's snapshot.
    A card view looks at it for an open word only."""

    def __init__(self, vocabulary: UserVocabulary) -> None:
        self._vocabulary = vocabulary

    def of(self, lemma: str) -> ElsewhereStatus | None:
        return self._vocabulary.of(lemma).elsewhere

    def of_lemmas(self, lemmas: Iterable[str]) -> dict[str, ElsewhereStatus | None]:
        """The same for many words, reading what the user knows once."""
        knowledge = self._vocabulary.knowledge()
        return {lemma: knowledge.of(lemma).elsewhere for lemma in lemmas}
