from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.candidate_factory import CandidateFactory
from backend.application.utils.manual_phrases import ManualPhrases
from backend.application.utils.source_free import ensure_source_free
from backend.domain.exceptions import SourceHasNoDocumentError, SourceNotFoundError
from backend.domain.services.document_layout import DocumentLayout

if TYPE_CHECKING:
    from backend.application.dto.candidate_dtos import SelectionDTO
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.application.utils.section_stamper import SectionStamper
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


class AddManualCandidateUseCase:
    """Adds the word the user selected during review as a card the user shows.

    The word is read by the same enrichment pipeline as automatic processing (lemma, POS,
    CEFR, frequency) but bypasses the CEFR level gate — it is always saved, as a phrase of its
    word by `ManualPhrases`.
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
        stamper: SectionStamper,
        lock: SourceOperationLock,
        card_views: CardViews,
        decide_phrase: DecidePhraseUseCase,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._lock = lock
        self._card_views = card_views
        self._source_repo = source_repo
        self._document_repo = document_repo
        self._candidate_factory = CandidateFactory(
            text_analyzer=text_analyzer,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
            phrasal_verb_detector=phrasal_verb_detector,
        )
        self._phrase_reader = phrase_reader
        self._manual = ManualPhrases(candidate_repo, occurrence_repo, stamper, decide_phrase)

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
        return self._manual.show(card, layout.target_key(phrase_position, phrase))
