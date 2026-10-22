"""Use case: show the bare target instead of a card's phrase."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.application.utils.phrase_replacement import PhraseReplacement
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.phrase import Phrase


class ReplaceWithTargetUseCase:
    """The word's dictionary form ("give in", "procrastinate") takes the card's place as a
    new phrase of the word (`PhraseReplacement`); all of it is the target. It is final as it
    is: AI polish would grow it back into a sentence.
    """

    def __init__(
        self,
        replacement: PhraseReplacement,
        phrase_reader: PhraseReader,
        card_views: CardViews,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._replacement = replacement
        self._phrase_reader = phrase_reader
        self._card_views = card_views

    def execute(self, occurrence_id: int) -> CardDTO:
        """Answers with the new card: the ✨ that follows the replacement reaches it.
        The move is one write transaction."""
        with self._unit_of_work.write():
            target_id = self._replacement.replace(occurrence_id, self._read, polished=True)
        return self._card_views.one(target_id)

    def _read(self, word: StoredCandidate) -> Phrase:
        return self._phrase_reader.read(word.lemma, [(0, len(word.lemma))])
