from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.known_word_dtos import KnownWordDTO

if TYPE_CHECKING:
    from backend.domain.ports.known_word_repository import KnownWordRepository


class ManageKnownWordsUseCase:
    """Lists and deletes known-word whitelist entries."""

    def __init__(self, known_word_repo: KnownWordRepository) -> None:
        self._known_word_repo = known_word_repo

    def list_all(self) -> list[KnownWordDTO]:
        words = self._known_word_repo.list_all()
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
        self._known_word_repo.remove(known_word_id)
