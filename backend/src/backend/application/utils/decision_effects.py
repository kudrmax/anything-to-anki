"""What follows a row of the decision tables (design §2.8): the writes and the refreshes."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.source_free import ensure_source_free
from backend.domain.entities.word_decision import WordDecision
from backend.domain.services.decision_rules import Effect, on_known_removed
from backend.domain.value_objects.anki_binding import AnkiBinding
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.word_decision_repository import WordDecisionRepository
    from backend.domain.ports.word_state_repository import WordStateRepository
    from backend.domain.services.decision_rules import WordOutcome
    from backend.domain.value_objects.card_choice import WordState
    from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge


class _Applied:
    """One outcome being applied: the word before and after, and its facts."""

    def __init__(
        self, before: WordState, outcome: WordOutcome, word: StoredCandidate | None,
        knowledge_before: LemmaKnowledge, note_id: int | None,
    ) -> None:
        self.before = before
        self.outcome = outcome
        self.word = word
        self.knowledge_before = knowledge_before
        self.note_id = note_id

    @property
    def after(self) -> WordState:
        return self.outcome.word

    @property
    def lemma(self) -> str:
        return self.before.lemma


class DecisionEffects:
    """Applies a WordOutcome: stores the choices and the decision status, then runs each of
    its effects. REMOVE_KNOWN runs the Known removal (§2.7) over every other word of the
    lemma, under the locks of their sources; its REVOKE outcomes never remove Known again.
    """

    def __init__(
        self,
        word_states: WordStateRepository,
        vocabulary: UserVocabulary,
        decision_repo: WordDecisionRepository,
        anki_sync: AnkiSyncRepository,
        review_status: ReviewStatusUpdater,
        lock: SourceOperationLock,
    ) -> None:
        self._words = word_states
        self._vocabulary = vocabulary
        self._decisions = decision_repo
        self._anki_sync = anki_sync
        self._review_status = review_status
        self._lock = lock
        self._handlers: Mapping[Effect, Callable[[_Applied], None]] = {
            Effect.RELEASE: self._release,
            Effect.BIND: self._bind,
            Effect.MARK_KNOWN: self._mark_known,
            Effect.CALIBRATE: self._calibrate,
            Effect.FORGET_CALIBRATION: self._forget_calibration,
            Effect.REMOVE_KNOWN: self._remove_known,
            Effect.REFRESH_SOURCE: self._refresh_source,
            Effect.REFRESH_LEMMA: self._refresh_lemma,
        }

    def apply(
        self, before: WordState, outcome: WordOutcome, word: StoredCandidate | None = None,
        *, note_id: int | None = None,
    ) -> None:
        """`word`: the word's facts, for calibration; `note_id`: the note an export bound."""
        self._apply(_Applied(before, outcome, word, self._vocabulary.of(before.lemma), note_id))

    def known_removed(
        self, lemma: str, knowledge_before: LemmaKnowledge, acting_word: int | None = None,
    ) -> None:
        """§2.7 after Known of the lemma was removed some other way (a report's Unknown).
        `knowledge_before`: what the lemma was before the removal."""
        self._cascade(lemma, knowledge_before, acting_word)

    def _apply(self, applied: _Applied) -> None:
        self._words.save(applied.after)
        # A decision status is knowledge too: a Learn waits for export in every source.
        self._vocabulary.scope.invalidate()
        for effect in _ORDER:
            if effect in applied.outcome.effects:
                self._handlers[effect](applied)

    # ── effects ────────────────────────────────────────────────────────

    def _release(self, applied: _Applied) -> None:
        released = [
            card.card_id for card in applied.before.cards
            if card.binding is not None and applied.after.card(card.card_id).binding is None
        ]
        self._anki_sync.release(released, self._vocabulary.scope.now)
        self._vocabulary.scope.invalidate()

    def _bind(self, applied: _Applied) -> None:
        assert applied.note_id is not None, "an export binds the note it made or found"
        before = {card.card_id: card for card in applied.before.cards}
        for card in applied.after.cards:
            binding = card.binding
            if binding is None or before[card.card_id].binding is not None:
                continue
            self._anki_sync.bind(AnkiBinding(
                word_id=applied.after.word_id, phrase_id=card.card_id, note_id=applied.note_id,
                lemma=applied.lemma, pos=applied.after.pos, note_kind=binding.note_kind,
                learning_since=binding.learning_since,
            ))
        self._vocabulary.scope.invalidate()

    def _mark_known(self, applied: _Applied) -> None:
        self._vocabulary.mark_known(applied.lemma, applied.after.pos)

    def _calibrate(self, applied: _Applied) -> None:
        word = applied.word
        if word is None or not _calibrated(applied.lemma, word.is_phrasal_verb):
            return
        self._decisions.record(WordDecision(
            lemma=word.lemma,
            zipf_frequency=word.zipf_frequency,
            is_known=applied.outcome.status.after is WordStatus.KNOWN,
        ))

    def _forget_calibration(self, applied: _Applied) -> None:
        phrasal = applied.word.is_phrasal_verb if applied.word is not None else False
        if _calibrated(applied.lemma, phrasal):
            self._decisions.forget(applied.lemma)

    def _remove_known(self, applied: _Applied) -> None:
        self._cascade(applied.lemma, applied.knowledge_before, applied.before.word_id)

    def _refresh_source(self, applied: _Applied) -> None:
        self._review_status.refresh(applied.after.source_id)

    def _refresh_lemma(self, applied: _Applied) -> None:
        self._review_status.refresh_showing({applied.lemma.lower()})

    # ── Known removal (§2.7) ───────────────────────────────────────────

    def _cascade(
        self, lemma: str, knowledge_before: LemmaKnowledge, acting_word: int | None,
    ) -> None:
        """The acting word's own outcome is its press: the cascade reads the others, on the
        snapshot taken before Known was forgotten."""
        others = [word for word in self._words.of_lemma(lemma) if word.word_id != acting_word]
        for source_id in sorted({word.source_id for word in others}):
            ensure_source_free(self._lock, source_id)
        self._vocabulary.forget_every_pos(lemma)
        scope = self._vocabulary.scope
        removal = on_known_removed(
            knowledge_before, others, self._anki_sync.orphans(lemma), scope.now,
        )
        by_id = {word.word_id: word for word in others}
        for outcome in removal.words:
            self._apply(_Applied(
                by_id[outcome.word.word_id], outcome, None, knowledge_before, None,
            ))
        self._anki_sync.release_rows(removal.released_orphans, scope.now)
        scope.invalidate()


# Writes first, then what reads them: the cascade reads the bindings left by the release.
_ORDER = (
    Effect.RELEASE, Effect.BIND, Effect.MARK_KNOWN, Effect.CALIBRATE,
    Effect.FORGET_CALIBRATION, Effect.REMOVE_KNOWN, Effect.REFRESH_SOURCE,
    Effect.REFRESH_LEMMA,
)


def _calibrated(lemma: str, is_phrasal_verb: bool) -> bool:
    """Only single words: a phrase's frequency is not comparable with a word's."""
    return not is_phrasal_verb and " " not in lemma
