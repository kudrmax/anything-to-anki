"""Use case: show one of the AI-generated examples instead of a card's phrase."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.topic_phrase_selection import parse_marked_phrase

if TYPE_CHECKING:
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.application.utils.phrase_replacement import PhraseReplacement
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.phrase import Phrase


class ReplaceWithExampleUseCase:
    """The example takes the card's place as a new phrase of its word (`PhraseReplacement`).

    The example comes as AI wrote it: its **bold** words are the target; without them the
    target is found by the word's dictionary form.
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

    def execute(self, occurrence_id: int, example_text: str) -> CardDTO:
        """Answers with the example's card: the ✨ that follows the replacement reaches it.
        The move is one write transaction."""
        stripped = example_text.strip()
        if not stripped:
            msg = "example_text must not be empty"
            raise ValueError(msg)

        def read(word: StoredCandidate) -> Phrase:
            marked = parse_marked_phrase(stripped)
            if marked is not None:
                return self._phrase_reader.read(marked.text, marked.spans)
            return self._phrase_reader.read_for(stripped, word.lemma)

        with self._unit_of_work.write():
            example_id = self._replacement.replace(occurrence_id, read)
        return self._card_views.one(example_id)
