from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.application.utils.section_stamper import SectionStamper
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.services.candidate_sections import WordFacts
    from backend.domain.value_objects.phrase import Phrase


class RewritePhrase:
    """The one way a phrase gets a new text for its phrase — from AI, by hand, or any other.

    The target is found in the new text by the card's dictionary form, so the text may
    change its forms ("scattered" → "scatters"). Without the target the text is refused
    with TargetNotInPhraseError and the card keeps its phrase.
    """

    def __init__(
        self,
        phrase_reader: PhraseReader,
        occurrence_repo: OccurrenceRepository,
        stamper: SectionStamper,
    ) -> None:
        self._occurrence_repo = occurrence_repo
        self._phrase_reader = phrase_reader
        self._stamper = stamper

    def of_phrase(self, occurrence: Occurrence, word: WordFacts, text: str) -> Phrase:
        """The new text of one phrase of `word`; the phrase earns its section anew."""
        phrase = self.read(word, text)
        self.store(occurrence, word, phrase)
        return phrase

    def read(self, word: WordFacts, text: str) -> Phrase:
        """`text` read as a phrase of `word`, without storing it: the slow part, kept out of
        a write by callers that rewrite many phrases."""
        return self._phrase_reader.read_for(text, word.lemma)

    def store(self, occurrence: Occurrence, word: WordFacts, phrase: Phrase) -> None:
        """Stores `phrase`, read by `read`, as the phrase's new text."""
        assert occurrence.id is not None
        self._occurrence_repo.write_text(
            occurrence.id, occurrence.source_phrase, occurrence.phrase_position,
            earned_section=self._stamper.earned(phrase, word),
            polished=phrase,
        )
