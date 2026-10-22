from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.source_free import ensure_source_free
from backend.domain.entities.job import Job
from backend.domain.entities.occurrence import Occurrence
from backend.domain.exceptions import PhraseNotFoundError
from backend.domain.services.decision_rules import move
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.application.utils.decision_effects import DecisionEffects
    from backend.application.utils.section_stamper import SectionStamper
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.word_state_repository import WordStateRepository
    from backend.domain.value_objects.phrase import Phrase


class PhraseReplacement:
    """A new `example` phrase of the card's word, shown by the user, takes the card's place;
    the replaced phrase is no longer shown. The decision of the word moves to the new phrase
    by the move table (`decision_rules.move`), kind and all: a Known stays Known, a card in
    Anki gives its decision to the new phrase and releases its binding (the next export binds
    the new phrase to the same note).

    The new phrase stands for the selection card if it replaced it, or replaced a phrase that
    stood for it: the selection then shows no other card of the word.

    Its meaning is queued at once: the card is useless without it. Its speech is made for
    its own text, like for any phrase without one.
    """

    def __init__(
        self,
        occurrence_repo: OccurrenceRepository,
        candidate_repo: CandidateRepository,
        stamper: SectionStamper,
        job_repo: JobRepository,
        lock: SourceOperationLock,
        word_states: WordStateRepository,
        vocabulary: UserVocabulary,
        effects: DecisionEffects,
    ) -> None:
        self._occurrences = occurrence_repo
        self._candidate_repo = candidate_repo
        self._stamper = stamper
        self._job_repo = job_repo
        self._lock = lock
        self._word_states = word_states
        self._vocabulary = vocabulary
        self._effects = effects

    def replace(
        self,
        occurrence_id: int,
        read: Callable[[StoredCandidate], Phrase],
        *,
        polished: bool = False,
    ) -> int:
        """`read` makes the new phrase of the word. A `polished` phrase is final as it is:
        AI polish leaves it alone. Runs inside the caller's write; returns the new phrase."""
        replaced = self._occurrences.get(occurrence_id)
        word = (
            self._candidate_repo.get_by_id(replaced.candidate_id)
            if replaced is not None else None
        )
        if replaced is None or word is None:
            raise PhraseNotFoundError(occurrence_id)
        ensure_source_free(self._lock, word.source_id)
        phrase = read(word)

        made = self._occurrences.add(Occurrence(
            candidate_id=replaced.candidate_id,
            origin=OccurrenceOrigin.EXAMPLE,
            source_phrase=phrase,
            phrase_position=None,
            key=None,
            fragment_score=None,
            earned_section=self._stamper.earned(phrase, word),
            shown_by=ShownBy.USER,
            replaces_selection=_stands_for_selection(replaced),
            polished_phrase=phrase if polished else None,
        ))
        assert made.id is not None
        self._occurrences.set_shown([occurrence_id], None)
        state = self._word_states.of_word(replaced.candidate_id)
        assert state is not None
        outcome = move(
            state, occurrence_id, made.id, self._vocabulary.of(word.lemma),
            self._vocabulary.scope.now,
        )
        self._effects.apply(state, outcome, word)
        self._job_repo.enqueue([Job.queued(
            JobType.MEANING, word.source_id, replaced.candidate_id,
            phrase_id=made.id, phrase_revision=made.revision,
        )])
        return made.id


def _stands_for_selection(replaced: Occurrence) -> bool:
    return replaced.shown_by is ShownBy.SELECTION or (
        replaced.is_shown and replaced.replaces_selection
    )
