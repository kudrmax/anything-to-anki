from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.services.card_view import CHOSEN_TO_LEARN, in_export_queue
from backend.domain.services.export_readiness import export_group
from backend.domain.value_objects.card_choice import (
    DecisionStatus,
    NoteKind,
    decision_status,
    export_kind,
)
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from collections.abc import Collection

    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.word_state_repository import WordStateRepository
    from backend.domain.services.cloze_builder import ClozeBuilder
    from backend.domain.value_objects.card_choice import WordState
    from backend.domain.value_objects.export_group import ExportGroup

logger = logging.getLogger(__name__)

_CHOSEN_STATUSES = tuple(WordStatus(status.value) for status in CHOSEN_TO_LEARN)


@dataclass(frozen=True)
class ExportCard:
    """A word to learn and the phrase of its decision: one note in Anki.

    The phrase gives the sentence and everything made for it; the word, the target, its
    pronunciation and picture. `state` is the word as the decision tables see it: the export
    binds its decision card (S1).
    """

    word: StoredCandidate
    phrase: Occurrence
    state: WordState

    @property
    def word_id(self) -> int:
        assert self.word.id is not None
        return self.word.id

    @property
    def phrase_id(self) -> int:
        assert self.phrase.id is not None
        return self.phrase.id

    @property
    def is_cloze(self) -> bool:
        return export_kind(self.phrase.card_state) is NoteKind.CLOZE

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
    """Words in the export queue, plus how many of the chosen ones are in Anki already."""

    pending: list[ExportCard]
    exported_count: int

    def in_group(self, group: ExportGroup) -> list[ExportCard]:
        return [card for card in self.pending if export_group(card.phrase) == group]


class ExportQueue:
    """The words chosen to learn, split into the export queue (`in_export_queue`: Learn not
    in Anki yet, unless its lemma was put in Known since) and those in Anki; a word goes with
    the phrase of its decision, as `export_kind` says."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        occurrence_repo: OccurrenceRepository,
        word_states: WordStateRepository,
        vocabulary: UserVocabulary,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._occurrences = occurrence_repo
        self._word_states = word_states
        self._vocabulary = vocabulary

    def for_source(self, source_id: int) -> ExportBatch:
        words = self._candidate_repo.get_by_source(source_id)
        return self._split([w for w in words if w.status in _CHOSEN_STATUSES])

    def for_all(self) -> ExportBatch:
        return self._split(self._chosen())

    def for_sources(self, source_ids: Collection[int]) -> ExportBatch:
        return self._split([w for w in self._chosen() if w.source_id in source_ids])

    def _chosen(self) -> list[StoredCandidate]:
        found = [
            word for status in _CHOSEN_STATUSES
            for word in self._candidate_repo.get_all_by_status(status)
        ]
        return sorted(found, key=lambda w: (w.source_id, w.id or 0))

    def _split(self, chosen: list[StoredCandidate]) -> ExportBatch:
        decisions = self._occurrences.decision_phrases([w.id for w in chosen if w.id is not None])
        states: dict[int, WordState] = {}
        for source_id in sorted({word.source_id for word in chosen}):
            states.update(self._word_states.of_source(source_id))
        now = self._vocabulary.scope.now
        pending: list[ExportCard] = []
        exported_count = 0
        for word in chosen:
            phrase = decisions.get(word.id) if word.id is not None else None
            state = states.get(word.id) if word.id is not None else None
            if phrase is None or state is None:
                logger.warning("export: word %s chosen to learn has no decision card", word.id)
            elif in_export_queue(state, self._vocabulary.of(word.lemma), now):
                pending.append(ExportCard(word=word, phrase=phrase, state=state))
            elif decision_status(state) is DecisionStatus.LEARNING:
                exported_count += 1
        return ExportBatch(pending=pending, exported_count=exported_count)
