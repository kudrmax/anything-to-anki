from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.services.export_readiness import export_group
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.phrase_origin_kind import DecisionKind

if TYPE_CHECKING:
    from collections.abc import Collection

    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.services.cloze_builder import ClozeBuilder
    from backend.domain.value_objects.export_group import ExportGroup

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportCard:
    """A word to learn and the phrase of its decision: one note in Anki.

    The phrase gives the sentence and everything made for it; the word, the target, its
    pronunciation and picture.
    """

    word: StoredCandidate
    phrase: Occurrence

    @property
    def is_cloze(self) -> bool:
        return self.phrase.decision_kind is DecisionKind.CLOZE

    def cloze_markup(self, builder: ClozeBuilder) -> CandidateCloze | None:
        """The words a cloze card hides; none for a plain card. A cloze decided without
        markup hides the target."""
        if not self.is_cloze:
            return None
        phrase = self.phrase.phrase
        made = builder.effective_for(phrase, self.phrase.cloze)
        if made is not None:
            return made
        return CandidateCloze(
            candidate_id=self.phrase.candidate_id,
            hidden_word_indices=builder.default_hidden(phrase),
            hint_kind=ClozeHintKind.NONE,
            custom_hint=None,
            phrase=phrase.text,
        )


@dataclass(frozen=True)
class ExportBatch:
    """'Learn' words still waiting for export, plus how many already went to Anki."""

    pending: list[ExportCard]
    exported_count: int

    def in_group(self, group: ExportGroup) -> list[ExportCard]:
        return [card for card in self.pending if export_group(card.phrase) == group]


class ExportQueue:
    """Splits 'learn' words into not yet exported and already sent to Anki; a word goes
    with the phrase of its decision."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        anki_sync_repo: AnkiSyncRepository,
        occurrence_repo: OccurrenceRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._anki_sync_repo = anki_sync_repo
        self._occurrences = occurrence_repo

    def for_source(self, source_id: int) -> ExportBatch:
        words = self._candidate_repo.get_by_source(source_id)
        return self._split([w for w in words if w.status == CandidateStatus.LEARN])

    def for_all(self) -> ExportBatch:
        return self._split(self._candidate_repo.get_all_by_status(CandidateStatus.LEARN))

    def for_sources(self, source_ids: Collection[int]) -> ExportBatch:
        learn = self._candidate_repo.get_all_by_status(CandidateStatus.LEARN)
        return self._split([w for w in learn if w.source_id in source_ids])

    def _split(self, learn: list[StoredCandidate]) -> ExportBatch:
        word_ids = [w.id for w in learn if w.id is not None]
        exported = self._anki_sync_repo.get_synced_candidate_ids(word_ids)
        waiting = [w for w in learn if w.id not in exported]
        decisions = self._occurrences.decision_phrases(
            [w.id for w in waiting if w.id is not None],
        )
        pending: list[ExportCard] = []
        for word in waiting:
            phrase = decisions.get(word.id) if word.id is not None else None
            if phrase is None:
                logger.warning("export: learn word %s has no decision phrase", word.id)
                continue
            pending.append(ExportCard(word=word, phrase=phrase))
        return ExportBatch(pending=pending, exported_count=len(learn) - len(waiting))
