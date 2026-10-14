"""Use case: show one of the AI-generated examples instead of a card's phrase."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.source_free import ensure_source_free
from backend.domain.entities.job import Job
from backend.domain.entities.occurrence import Occurrence
from backend.domain.exceptions import AlreadyInAnkiError, PhraseNotFoundError
from backend.domain.services.topic_phrase_selection import parse_marked_phrase
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy

if TYPE_CHECKING:
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock


class ReplaceWithExampleUseCase:
    """The example becomes a new `example` phrase of the card's word, shown by the user; the
    replaced phrase is no longer shown. The decision of the word moves to the example, kind
    and all, unless it is already in Anki.

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
        review_status: ReviewStatusUpdater,
        phrase_reader: PhraseReader,
        job_repo: JobRepository,
        lock: SourceOperationLock,
        card_views: CardViews,
    ) -> None:
        self._lock = lock
        self._card_views = card_views
        self._occurrences = occurrence_repo
        self._candidate_repo = candidate_repo
        self._review_status = review_status
        self._phrase_reader = phrase_reader
        self._job_repo = job_repo

    def execute(self, occurrence_id: int, example_text: str) -> CardDTO:
        """Answers with the example's card: the ✨ that follows the replacement reaches it."""
        stripped = example_text.strip()
        if not stripped:
            msg = "example_text must not be empty"
            raise ValueError(msg)

        replaced = self._occurrences.get(occurrence_id)
        word = (
            self._candidate_repo.get_by_id(replaced.candidate_id)
            if replaced is not None else None
        )
        if replaced is None or word is None:
            raise PhraseNotFoundError(occurrence_id)
        ensure_source_free(self._lock, word.source_id)
        if replaced.is_decision and replaced.exported:
            raise AlreadyInAnkiError(occurrence_id)
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
            shown_by=ShownBy.USER,
            replaces_selection=_stands_for_selection(replaced),
        ))
        assert example.id is not None
        self._occurrences.set_shown([occurrence_id], None)
        if replaced.is_decision:
            self._occurrences.set_decision(
                replaced.candidate_id, example.id, replaced.decision_kind,
            )
        self._job_repo.enqueue([Job.queued(
            JobType.MEANING, word.source_id, replaced.candidate_id,
            phrase_id=example.id, phrase_revision=example.revision,
        )])
        self._review_status.refresh(word.source_id)
        return self._card_views.one(example.id)


def _stands_for_selection(replaced: Occurrence) -> bool:
    return replaced.shown_by is ShownBy.SELECTION or (
        replaced.is_shown and replaced.replaces_selection
    )
