from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.services.card_view import in_export_queue, learning_in_anki
from backend.domain.services.export_readiness import export_group
from backend.domain.value_objects.card_choice import is_cloze
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind

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
        return is_cloze(self.phrase.card_state)

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

    def for_all(self) -> ExportBatch:
        return self._split(self._chosen(None))

    def for_sources(self, source_ids: Collection[int]) -> ExportBatch:
        return self._split(self._chosen(source_ids))

    def pending_count(self) -> int:
        """How many words the queue holds, read without their phrases."""
        chosen = self._candidate_repo.chosen_to_learn(None)
        states = self._word_states.of_words([w.id for w in chosen if w.id is not None])
        now = self._vocabulary.scope.now
        return sum(
            in_export_queue(state, self._vocabulary.of(state.lemma), now)
            for state in states.values()
        )

    def _chosen(self, source_ids: Collection[int] | None) -> list[StoredCandidate]:
        found = self._candidate_repo.chosen_to_learn(source_ids)
        return sorted(found, key=lambda w: (w.source_id, w.id or 0))

    def _split(self, chosen: list[StoredCandidate]) -> ExportBatch:
        decisions = self._occurrences.decision_phrases([w.id for w in chosen if w.id is not None])
        states = self._word_states.of_words([w.id for w in chosen if w.id is not None])
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
            elif learning_in_anki(state):
                exported_count += 1
        return ExportBatch(pending=pending, exported_count=exported_count)
