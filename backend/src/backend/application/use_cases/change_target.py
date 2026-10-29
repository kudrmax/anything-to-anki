"""Use case: the user picks other words of a card's phrase as its target."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.utils.candidate_factory import CandidateFactory
from backend.application.utils.manual_phrases import ManualPhrases
from backend.application.utils.source_free import ensure_source_free
from backend.domain.entities.job import Job
from backend.domain.exceptions import (
    PhraseNotFoundError,
    TargetChangeRefusedError,
    TargetNotInPhraseError,
)
from backend.domain.services.card_view import can_change_target, is_decided
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.services.phrase_selection import SelectionScore, select_phrases
from backend.domain.services.target_transfer import target_in
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.new_card import NewCard
from backend.domain.value_objects.phrase_origin_kind import ShownBy

if TYPE_CHECKING:
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.section_stamper import SectionStamper
    from backend.domain.entities.occurrence import Occurrence, OccurrenceKey
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.ports.word_state_repository import WordStateRepository
    from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
    from backend.domain.value_objects.phrase import Phrase

logger = logging.getLogger(__name__)


class ChangeTargetUseCase:
    """The user picks other words of the card's phrase as its target: the card is made anew.

    The words are picked in the text the card shows, edited or polished, so a word the user
    wrote in is a target too. The new card shows the same text with the new target as a
    phrase of the target's word (`ManualPhrases`), with nothing made for it: its meaning is
    queued at once, as for any replacing card. A target the phrase cut from the source holds
    keeps the card's place in the document; a target only the rewritten text holds makes a
    phrase with no place. A rewritten text is final as it is: AI polish leaves it alone.

    The old card is removed by the user (`remove_card`), so neither the selection nor a
    rebuild brings it back; its word's selection is made again at once. A card with a
    decision is refused (TargetChangeRefusedError): the decision is its word's.
    """

    def __init__(
        self,
        occurrence_repo: OccurrenceRepository,
        candidate_repo: CandidateRepository,
        document_repo: DocumentRepository,
        job_repo: JobRepository,
        word_states: WordStateRepository,
        text_analyzer: TextAnalyzer,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        phrasal_verb_detector: PhrasalVerbDetector,
        stamper: SectionStamper,
        lock: SourceOperationLock,
        card_views: CardViews,
        decide_phrase: DecidePhraseUseCase,
        unit_of_work: UnitOfWork,
        weight_unknown: int,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._occurrences = occurrence_repo
        self._candidate_repo = candidate_repo
        self._document_repo = document_repo
        self._job_repo = job_repo
        self._word_states = word_states
        self._stamper = stamper
        self._lock = lock
        self._card_views = card_views
        self._weight_unknown = weight_unknown
        self._candidate_factory = CandidateFactory(
            text_analyzer=text_analyzer,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
            phrasal_verb_detector=phrasal_verb_detector,
        )
        self._manual = ManualPhrases(candidate_repo, occurrence_repo, stamper, decide_phrase)

    def execute(self, occurrence_id: int, target_words: list[int]) -> CardDTO:
        """`target_words`: numbers of the words of the phrase the card shows. Answers with
        the new card; the change is one write transaction."""
        with self._unit_of_work.write():
            card_id = self._change(occurrence_id, tuple(sorted(set(target_words))))
        return self._card_views.one(card_id)

    def _change(self, occurrence_id: int, target: tuple[int, ...]) -> int:
        old = self._occurrences.get(occurrence_id)
        word = self._candidate_repo.get_by_id(old.candidate_id) if old is not None else None
        if old is None or word is None:
            raise PhraseNotFoundError(occurrence_id)
        ensure_source_free(self._lock, word.source_id)
        state = self._word_states.of_word(old.candidate_id)
        assert state is not None
        if not can_change_target(state.card(occurrence_id)):
            raise TargetChangeRefusedError(occurrence_id)
        shown = _retargeted(old.phrase, target)
        if shown.target == old.phrase.target:
            return occurrence_id

        self._retire(old)
        made = self._make(old, shown, word.source_id)
        made_phrase = self._occurrences.get(made)
        assert made_phrase is not None
        if made_phrase.candidate_id == old.candidate_id and _stands_for_selection(old):
            self._occurrences.set_replaces_selection(made, True)
        self._reselect(old.candidate_id)
        self._job_repo.enqueue([Job.queued(
            JobType.MEANING, word.source_id, made_phrase.candidate_id,
            phrase_id=made, phrase_revision=made_phrase.revision,
        )])
        logger.info(
            "Changed target of phrase %d: %r → %r (phrase %d)",
            occurrence_id, old.phrase.target_text(), shown.target_text(), made,
        )
        return made

    def _retire(self, old: Occurrence) -> None:
        assert old.id is not None
        self._occurrences.remove_card(old.id)
        self._job_repo.cancel_for_phrases([old.id])

    def _make(self, old: Occurrence, shown: Phrase, source_id: int) -> int:
        document = self._document_repo.get(source_id)
        layout = DocumentLayout(document) if document is not None else None
        in_source = (
            target_in(old.source_phrase, shown) if old.phrase_position is not None else None
        )
        occurrences = 1
        if layout is not None:
            occurrences = max(layout.text.lower().count(shown.target_text().lower()), 1)
        if in_source is None:
            card = self._candidate_factory.build(
                source_id=source_id, phrase=shown, occurrences=occurrences,
            )
            return self._manual.show(card, None, polished=shown, instead_of=old.id)
        phrase = old.source_phrase.with_target(in_source)
        assert old.phrase_position is not None
        built = self._candidate_factory.build(
            source_id=source_id, phrase=shown, occurrences=occurrences,
        )
        card = NewCard(word=built.word, phrase=phrase, position=old.phrase_position)
        key: OccurrenceKey | None = (
            layout.target_key(old.phrase_position, phrase) if layout is not None else None
        )
        polished = shown if shown.text != phrase.text else None
        return self._manual.show(card, key, polished=polished, instead_of=old.id)

    def _reselect(self, word_id: int) -> None:
        """The selection of the word as a rebuild would make it now."""
        state = self._word_states.of_word(word_id)
        assert state is not None
        change = select_phrases(
            self._occurrences.word_projection(word_id),
            is_decided(state),
            SelectionScore(self._stamper.rule().knowledge, self._weight_unknown),
        )
        self._occurrences.set_shown(list(change.clear_selection), None)
        if change.set_selection is not None:
            self._occurrences.set_shown([change.set_selection], ShownBy.SELECTION)


def _stands_for_selection(old: Occurrence) -> bool:
    return old.shown_by is ShownBy.SELECTION or (old.is_shown and old.replaces_selection)


def _retargeted(phrase: Phrase, target: tuple[int, ...]) -> Phrase:
    try:
        return phrase.with_target(target)
    except ValueError as e:
        raise TargetNotInPhraseError() from e
