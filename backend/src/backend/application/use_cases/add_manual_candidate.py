from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.candidate_factory import CandidateFactory
from backend.application.utils.source_free import ensure_source_free
from backend.domain.entities.occurrence import Occurrence
from backend.domain.exceptions import SourceHasNoDocumentError, SourceNotFoundError
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.card_choice import Press, is_skipped
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy

if TYPE_CHECKING:
    from backend.application.dto.candidate_dtos import SelectionDTO
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.domain.entities.occurrence import OccurrenceKey
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
    from backend.domain.value_objects.new_card import NewCard


class AddManualCandidateUseCase:
    """Adds the word the user selected during review as a card the user shows.

    The word is read by the same enrichment pipeline as automatic processing (lemma, POS,
    CEFR, frequency) but bypasses the CEFR level gate — it is always saved. A word the source
    already has gets another phrase; at the place of one of its auto phrases, or of a manual
    phrase with the same text, that phrase is shown instead of a duplicate (and if it was the
    selection card, it keeps standing for it; a skipped one is unskipped by pressing Skip,
    unless its word is decided elsewhere: then it stays done).
    The phrase keeps its place in the document as its key, so Rebuild finds it.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        candidate_repo: CandidateRepository,
        occurrence_repo: OccurrenceRepository,
        text_analyzer: TextAnalyzer,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        phrasal_verb_detector: PhrasalVerbDetector,
        phrase_reader: PhraseReader,
        lock: SourceOperationLock,
        card_views: CardViews,
        decide_phrase: DecidePhraseUseCase,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._lock = lock
        self._decide_phrase = decide_phrase
        self._card_views = card_views
        self._source_repo = source_repo
        self._document_repo = document_repo
        self._candidate_repo = candidate_repo
        self._occurrences = occurrence_repo
        self._candidate_factory = CandidateFactory(
            text_analyzer=text_analyzer,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
            phrasal_verb_detector=phrasal_verb_detector,
        )
        self._phrase_reader = phrase_reader

    def execute(
        self,
        source_id: int,
        target_words: list[int],
        selection: SelectionDTO,
    ) -> CardDTO:
        """The phrase is the selected piece of the document; the target, the picked words in it.
        Answers with the card of that phrase. The add, and its unskip, are one write
        transaction."""
        with self._unit_of_work.write():
            phrase_id = self._add(source_id, target_words, selection)
        return self._card_views.one(phrase_id)

    def _add(self, source_id: int, target_words: list[int], selection: SelectionDTO) -> int:
        if self._source_repo.get_by_id(source_id) is None:
            raise SourceNotFoundError(source_id)
        ensure_source_free(self._lock, source_id)
        document = self._document_repo.get(source_id)
        if document is None:
            raise SourceHasNoDocumentError(source_id)
        layout = DocumentLayout(document)
        phrase_position = layout.selected(selection.start, selection.end)
        phrase = self._phrase_reader.read_picked(layout.fragment(phrase_position), target_words)
        occurrences = max(layout.text.lower().count(phrase.target_text().lower()), 1)

        card = self._candidate_factory.build(
            source_id=source_id, phrase=phrase, occurrences=occurrences,
            position=phrase_position,
        )
        key = layout.target_key(phrase_position, phrase)
        word_id = self._word_of(card.word)
        if word_id is None:
            word_id = self._candidate_repo.add_word(card.word)
            return self._add_phrase(word_id, card, key)
        return self._show_at(word_id, card, key)

    def _word_of(self, word: StoredCandidate) -> int | None:
        return self._candidate_repo.word_id(
            word.source_id, WordKey.of(word.lemma, word.is_phrasal_verb),
        )

    def _show_at(self, word_id: int, card: NewCard, key: OccurrenceKey) -> int:
        existing = next(
            (
                o for o in self._occurrences.of_word(word_id)
                if o.key == key and (
                    o.origin is OccurrenceOrigin.AUTO
                    or (
                        o.origin is OccurrenceOrigin.MANUAL
                        and o.source_phrase.text == card.phrase.text
                    )
                )
            ),
            None,
        )
        if existing is None:
            return self._add_phrase(word_id, card, key)
        assert existing.id is not None
        if existing.shown_by is ShownBy.SELECTION:
            self._occurrences.set_replaces_selection(existing.id, True)
        self._occurrences.set_shown([existing.id], ShownBy.USER)
        if is_skipped(existing.card_state):
            self._decide_phrase.press_unless_done(existing.id, Press.SKIP)
        return existing.id

    def _add_phrase(self, word_id: int, card: NewCard, key: OccurrenceKey) -> int:
        added = self._occurrences.add(Occurrence(
            candidate_id=word_id,
            origin=OccurrenceOrigin.MANUAL,
            source_phrase=card.phrase,
            phrase_position=card.position,
            key=key,
            fragment_score=None,
            shown_by=ShownBy.USER,
        ))
        assert added.id is not None
        return added.id

