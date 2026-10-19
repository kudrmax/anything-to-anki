from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import InAnkiWordDTO, LearningWordsDTO

if TYPE_CHECKING:
    from backend.application.utils.user_vocabulary import UserVocabulary


class GetLearningWordsUseCase:
    """The words the user is learning, for reading: those in Anki, with the day each turns
    Known, and those awaiting export."""

    def __init__(self, vocabulary: UserVocabulary) -> None:
        self._vocabulary = vocabulary

    def execute(self) -> LearningWordsDTO:
        lemmas = list(self._vocabulary.knowledge().lemmas())
        return LearningWordsDTO(
            in_anki=[
                InAnkiWordDTO(lemma=lemma, known_on=knowledge.timer_known_on)
                for lemma, knowledge in lemmas
                if knowledge.is_learning and knowledge.timer_known_on is not None
            ],
            awaiting_export=[lemma for lemma, knowledge in lemmas if knowledge.is_learn],
        )
