from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.known_word_dtos import KnownWordDTO

if TYPE_CHECKING:
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.application.utils.user_vocabulary import UserVocabulary


class ManageKnownWordsUseCase:
    """Lists and deletes known-word whitelist entries."""

    def __init__(self, vocabulary: UserVocabulary, review_status: ReviewStatusUpdater) -> None:
        self._vocabulary = vocabulary
        self._review_status = review_status

    def list_all(self) -> list[KnownWordDTO]:
        words = self._vocabulary.known_words()
        return [
            KnownWordDTO(
                id=w.id,  # type: ignore[arg-type]
                lemma=w.lemma,
                pos=w.pos,
                created_at=w.created_at,
            )
            for w in words
        ]

    def delete(self, known_word_id: int) -> None:
        self._vocabulary.remove_known(known_word_id)
        self._review_status.refresh_all()

    def add_bulk(self, lemmas: list[str]) -> None:
        """Add multiple words as known (pos=None, meaning known for any POS)."""
        for lemma in lemmas:
            self._vocabulary.mark_known(lemma, None)
        self._review_status.refresh_all()
