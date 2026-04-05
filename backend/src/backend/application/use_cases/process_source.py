from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.analysis_dtos import AnalyzeTextRequest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import SourceAlreadyProcessedError, SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.source_type import SourceType

if TYPE_CHECKING:
    from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.dictionary_provider import DictionaryProvider
    from backend.domain.ports.known_word_repository import KnownWordRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.source_parser import SourceParser
    from backend.domain.ports.source_repository import SourceRepository

_ALLOWED_START_STATUSES = frozenset({SourceStatus.NEW, SourceStatus.ERROR})


class ProcessSourceUseCase:
    """Orchestrates async source processing: validates, runs pipeline, saves results."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        known_word_repo: KnownWordRepository,
        settings_repo: SettingsRepository,
        analyze_text_use_case: AnalyzeTextUseCase,
        dictionary_provider: DictionaryProvider,
        source_parsers: dict[SourceType, SourceParser] | None = None,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._known_word_repo = known_word_repo
        self._settings_repo = settings_repo
        self._analyze_text = analyze_text_use_case
        self._dictionary_provider = dictionary_provider
        self._source_parsers: dict[SourceType, SourceParser] = source_parsers or {}

    def start(self, source_id: int) -> None:
        """Validate source and mark as PROCESSING. Call before launching background task."""
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.status not in _ALLOWED_START_STATUSES:
            raise SourceAlreadyProcessedError(source_id)
        self._source_repo.update_status(source_id, SourceStatus.PROCESSING)

    def execute(self, source_id: int) -> None:
        """Run the full pipeline and save results. Call in background thread."""
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)

        cefr_level = self._settings_repo.get("cefr_level", "B1") or "B1"
        parser = self._source_parsers.get(source.source_type)
        raw_text = parser.parse(source.raw_text) if parser else source.raw_text
        request = AnalyzeTextRequest(
            raw_text=raw_text,
            user_level=cefr_level,
        )
        result = self._analyze_text.execute(request)

        known_pairs = self._known_word_repo.get_all_pairs()
        filtered = [c for c in result.candidates if (c.lemma, c.pos) not in known_pairs]

        _NO_DEFINITION = "No definition found"
        stored: list[StoredCandidate] = []
        for c in filtered:
            entry = self._dictionary_provider.get_entry(c.lemma, c.pos)
            definition = entry.definition if entry.definition != _NO_DEFINITION else None
            stored.append(
                StoredCandidate(
                    source_id=source_id,
                    lemma=c.lemma,
                    pos=c.pos,
                    cefr_level=c.cefr_level,
                    zipf_frequency=c.zipf_frequency,
                    is_sweet_spot=c.is_sweet_spot,
                    context_fragment=c.context_fragment,
                    fragment_purity=c.fragment_purity,
                    occurrences=c.occurrences,
                    surface_form=c.surface_form,
                    is_phrasal_verb=c.is_phrasal_verb,
                    status=CandidateStatus.PENDING,
                    definition=definition,
                    ipa=entry.ipa,
                ),
            )
        self._candidate_repo.create_batch(stored)
        self._source_repo.update_status(
            source_id, SourceStatus.DONE, cleaned_text=result.cleaned_text,
        )
