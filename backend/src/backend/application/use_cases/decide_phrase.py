from __future__ import annotations

import contextlib
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.application.utils.source_free import ensure_source_free
from backend.domain.exceptions import ActionRefusedError, PhraseNotFoundError
from backend.domain.services.card_view import card_view, open_elsewhere
from backend.domain.services.decision_rules import press, rule
from backend.domain.value_objects.card_choice import Refusal
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.decision_effects import DecisionEffects
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.ports.word_state_repository import WordStateRepository
    from backend.domain.services.card_view import CardView
    from backend.domain.value_objects.card_choice import Press, WordState
    from backend.domain.value_objects.elsewhere import ElsewhereStatus


class DecidePhraseUseCase:
    """A press of Learn, Cloze, Known or Skip on a card (a phrase of a word).

    The rules are the press table (`decision_rules.press`); what follows a row — the known
    words, calibration, the Anki binding, the Known removal in every source and the review
    status — is `DecisionEffects`. A refused press raises ActionRefusedError.

    `decide` reads the word and writes the press in one write transaction, so two presses at
    once on two phrases of a word decide it once; `press` is that work for a use case that
    holds the transaction itself.
    """

    def __init__(
        self,
        occurrence_repo: OccurrenceRepository,
        candidate_repo: CandidateRepository,
        word_states: WordStateRepository,
        vocabulary: UserVocabulary,
        effects: DecisionEffects,
        lock: SourceOperationLock,
        card_views: CardViews,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._lock = lock
        self._card_views = card_views
        self._occurrences = occurrence_repo
        self._candidates = candidate_repo
        self._word_states = word_states
        self._vocabulary = vocabulary
        self._effects = effects

    def decide(self, occurrence_id: int, button: Press) -> CardDTO:
        """The press, answered with the card as it is after it."""
        with self._unit_of_work.write():
            self.press(occurrence_id, button)
        return self._card_views.one(occurrence_id)

    def view(self, occurrence_id: int) -> CardView:
        word, state = self._word(occurrence_id)
        return self._view(word, state, occurrence_id, self._elsewhere(word, state))

    def press(self, occurrence_id: int, button: Press) -> None:
        word, state = self._word(occurrence_id)
        self._press(word, state, occurrence_id, button, self._elsewhere(word, state))

    def press_unless_done(self, occurrence_id: int, button: Press) -> None:
        """A press the system makes for the user: on a card done because its word is
        decided elsewhere the table refuses it, and the card stays as it is."""
        with contextlib.suppress(ActionRefusedError):
            self.press(occurrence_id, button)

    def _press(
        self, word: StoredCandidate, state: WordState, occurrence_id: int, button: Press,
        elsewhere: ElsewhereStatus | None,
    ) -> None:
        knowledge, now = self._vocabulary.of(word.lemma), self._vocabulary.scope.now
        try:
            outcome = press(state, occurrence_id, button, knowledge, elsewhere, now)
        except ActionRefusedError as refused:
            view = card_view(state, occurrence_id, knowledge, elsewhere, now)
            raise ActionRefusedError(
                refused.card_id, refused.refusal,
                rule(_REASONS, (refused.refusal, view.shown.status)),
            ) from None
        self._effects.apply(state, outcome, word)

    def _view(
        self, word: StoredCandidate, state: WordState, occurrence_id: int,
        elsewhere: ElsewhereStatus | None,
    ) -> CardView:
        return card_view(
            state, occurrence_id, self._vocabulary.of(word.lemma), elsewhere,
            self._vocabulary.scope.now,
        )

    def _word(self, occurrence_id: int) -> tuple[StoredCandidate, WordState]:
        occ = self._occurrences.get(occurrence_id)
        word = self._candidates.get_by_id(occ.candidate_id) if occ is not None else None
        if word is None or word.id is None:
            raise PhraseNotFoundError(occurrence_id)
        ensure_source_free(self._lock, word.source_id)
        state = self._word_states.of_word(word.id)
        if state is None:
            raise PhraseNotFoundError(occurrence_id)
        return word, state

    def _elsewhere(self, word: StoredCandidate, state: WordState) -> ElsewhereStatus | None:
        return open_elsewhere(state, self._vocabulary.of(word.lemma))


_LEARNED_ON_OTHER_CARD = "Learned via another phrase: change it on that card"
_LEARNING_ELSEWHERE = "Already learning from another source"
# Why a press is refused, by the status the card shows.
_REASONS: Mapping[tuple[Refusal, WordStatus], str] = MappingProxyType({
    (Refusal.NOT_DECISION_CARD, WordStatus.LEARN): _LEARNED_ON_OTHER_CARD,
    (Refusal.NOT_DECISION_CARD, WordStatus.LEARNING): _LEARNED_ON_OTHER_CARD,
    (Refusal.NOT_DECISION_CARD, WordStatus.KNOWN):
        "Known via another phrase: change it on that card",
    (Refusal.DECIDED_ELSEWHERE, WordStatus.KNOWN): "Already known",
    (Refusal.DECIDED_ELSEWHERE, WordStatus.LEARNING): _LEARNING_ELSEWHERE,
    (Refusal.DECIDED_ELSEWHERE, WordStatus.LEARN): _LEARNING_ELSEWHERE,
})
