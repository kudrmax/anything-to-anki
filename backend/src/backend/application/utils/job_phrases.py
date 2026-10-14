from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.utils.generation_targets import GenerationCard

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.value_objects.phrase_ref import PhraseRef

logger = logging.getLogger(__name__)


class JobPhrases:
    """The phrases claimed jobs work on, as long as they are what the jobs were queued for.

    A Rebuild may change a phrase's text (a new revision) or delete it while its job runs.
    Such a job ends quietly: it gets no card here, and a result made meanwhile is not
    written — every writer asks `holds` right before writing.
    """

    def __init__(
        self, candidate_repo: CandidateRepository, occurrence_repo: OccurrenceRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._occurrence_repo = occurrence_repo

    def cards(self, phrases: list[PhraseRef]) -> list[GenerationCard]:
        """The cards of the phrases still at their jobs' revision, in the jobs' order."""
        current: list[Occurrence] = []
        for ref in phrases:
            occurrence = self._occurrence_repo.get(ref.phrase_id)
            if occurrence is None or occurrence.revision != ref.revision:
                logger.info(
                    "Phrase %d is gone or changed since its job was queued, nothing to do",
                    ref.phrase_id,
                )
                continue
            current.append(occurrence)
        words = {
            word.id: word
            for word in self._candidate_repo.get_by_ids(
                sorted({occurrence.candidate_id for occurrence in current}),
            )
        }
        return [
            GenerationCard(words[occurrence.candidate_id], occurrence)
            for occurrence in current
            if occurrence.candidate_id in words
        ]

    def card(self, phrase: PhraseRef) -> GenerationCard | None:
        found = self.cards([phrase])
        return found[0] if found else None

    def holds(self, card: GenerationCard) -> bool:
        """The card's phrase is still what its job was queued for, and stays so until the
        result is committed."""
        if self._occurrence_repo.holds_revision(card.phrase_id, card.phrase.revision):
            return True
        logger.info(
            "Phrase %d changed or went while its result was made, result dropped",
            card.phrase_id,
        )
        return False
