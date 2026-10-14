from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import LearningWordsDTO

if TYPE_CHECKING:
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.learning_query import LearningQuery


class GetLearningWordsUseCase:
    """The words the user is learning, for reading: those in Anki and those awaiting export."""

    def __init__(self, vocabulary: UserVocabulary, learning_query: LearningQuery) -> None:
        self._vocabulary = vocabulary
        self._learning = learning_query

    def execute(self) -> LearningWordsDTO:
        vocabulary = self._vocabulary.snapshot()
        in_anki = {lemma for lemma in self._learning.in_anki() if vocabulary.is_learning(lemma)}
        awaiting = {
            lemma for lemma in self._learning.awaiting_export()
            if vocabulary.is_learning(lemma) and lemma not in in_anki
        }
        return LearningWordsDTO(in_anki=sorted(in_anki), awaiting_export=sorted(awaiting))
