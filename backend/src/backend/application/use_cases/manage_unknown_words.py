from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.unknown_word_dtos import UnknownWordDTO

if TYPE_CHECKING:
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.unit_of_work import UnitOfWork


class ManageUnknownWordsUseCase:
    """Lists and deletes the words the user said they don't know."""

    def __init__(self, vocabulary: UserVocabulary, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work
        self._vocabulary = vocabulary

    def list_all(self) -> list[UnknownWordDTO]:
        return [
            UnknownWordDTO(
                id=w.id,  # type: ignore[arg-type]
                lemma=w.lemma,
                created_at=w.created_at,
            )
            for w in self._vocabulary.unknown_words()
        ]

    def delete(self, unknown_word_id: int) -> None:
        with self._unit_of_work.write():
            self._vocabulary.remove_unknown(unknown_word_id)
