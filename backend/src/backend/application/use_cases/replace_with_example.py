"""Use case: show one of the AI-generated examples instead of a card's phrase."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.source_free import ensure_source_free
from backend.domain.entities.job import Job
from backend.domain.entities.occurrence import Occurrence
from backend.domain.exceptions import PhraseNotFoundError
from backend.domain.services.decision_rules import move
from backend.domain.services.topic_phrase_selection import parse_marked_phrase
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy

if TYPE_CHECKING:
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.decision_effects import DecisionEffects
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.application.utils.section_stamper import SectionStamper
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.ports.word_state_repository import WordStateRepository


class ReplaceWithExampleUseCase:
    """The example becomes a new `example` phrase of the card's word, shown by the user; the
    replaced phrase is no longer shown. The decision of the word moves to the example by
    the move table (`decision_rules.move`), kind and all: a Known stays Known, a card in Anki
    gives its decision to the example and releases its binding (the next export binds the
    example to the same note).

    The example stands for the selection card if it replaced it, or replaced a phrase that
    stood for it: the selection then shows no other card of the word.

    The example comes as AI wrote it: its **bold** words are the target; without them the
    target is found by the word's dictionary form. Its meaning is queued at once: the card
    is useless without it.
    """

    def __init__(
        self,
        occurrence_repo: OccurrenceRepository,
        candidate_repo: CandidateRepository,
        phrase_reader: PhraseReader,
        stamper: SectionStamper,
        job_repo: JobRepository,
        lock: SourceOperationLock,
        card_views: CardViews,
        word_states: WordStateRepository,
        vocabulary: UserVocabulary,
        effects: DecisionEffects,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._lock = lock
        self._word_states = word_states
        self._vocabulary = vocabulary
        self._effects = effects
        self._card_views = card_views
        self._occurrences = occurrence_repo
        self._candidate_repo = candidate_repo
        self._phrase_reader = phrase_reader
        self._stamper = stamper
        self._job_repo = job_repo

    def execute(self, occurrence_id: int, example_text: str) -> CardDTO:
        """Answers with the example's card: the ✨ that follows the replacement reaches it.
        The move is one write transaction."""
        stripped = example_text.strip()
        if not stripped:
            msg = "example_text must not be empty"
            raise ValueError(msg)
        with self._unit_of_work.write():
            example_id = self._replace(occurrence_id, stripped)
        return self._card_views.one(example_id)

    def _replace(self, occurrence_id: int, stripped: str) -> int:
        replaced = self._occurrences.get(occurrence_id)
        word = (
            self._candidate_repo.get_by_id(replaced.candidate_id)
            if replaced is not None else None
        )
        if replaced is None or word is None:
            raise PhraseNotFoundError(occurrence_id)
        ensure_source_free(self._lock, word.source_id)
        marked = parse_marked_phrase(stripped)
        phrase = (
            self._phrase_reader.read(marked.text, marked.spans)
            if marked is not None
            else self._phrase_reader.read_for(stripped, word.lemma)
        )

        example = self._occurrences.add(Occurrence(
            candidate_id=replaced.candidate_id,
            origin=OccurrenceOrigin.EXAMPLE,
            source_phrase=phrase,
            phrase_position=None,
            key=None,
            fragment_score=None,
            earned_section=self._stamper.earned(phrase, word),
            shown_by=ShownBy.USER,
            replaces_selection=_stands_for_selection(replaced),
        ))
        assert example.id is not None
        self._occurrences.set_shown([occurrence_id], None)
        state = self._word_states.of_word(replaced.candidate_id)
        assert state is not None
        outcome = move(
            state, occurrence_id, example.id, self._vocabulary.of(word.lemma),
            self._vocabulary.scope.now,
        )
        self._effects.apply(state, outcome, word)
        self._job_repo.enqueue([Job.queued(
            JobType.MEANING, word.source_id, replaced.candidate_id,
            phrase_id=example.id, phrase_revision=example.revision,
        )])
        return example.id


def _stands_for_selection(replaced: Occurrence) -> bool:
    return replaced.shown_by is ShownBy.SELECTION or (
        replaced.is_shown and replaced.replaces_selection
    )
