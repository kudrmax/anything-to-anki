from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
from backend.application.use_cases.create_source import CreateSourceUseCase
from backend.application.use_cases.get_candidates import GetCandidatesUseCase
from backend.application.use_cases.get_sources import GetSourcesUseCase
from backend.application.use_cases.manage_known_words import ManageKnownWordsUseCase
from backend.application.use_cases.manage_settings import ManageSettingsUseCase
from backend.application.use_cases.mark_candidate import MarkCandidateUseCase
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.infrastructure.adapters.cefrpy_classifier import CefrpyCEFRClassifier
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer
from backend.infrastructure.adapters.wordfreq_frequency_provider import (
    WordfreqFrequencyProvider,
)
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import (
    SqlaSettingsRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import (
    SqlaSourceRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class Container:
    """Dependency injection container. Single point of assembly for all dependencies."""

    def __init__(self) -> None:
        self._text_cleaner = RegexTextCleaner()
        self._text_analyzer = SpaCyTextAnalyzer()
        self._cefr_classifier = CefrpyCEFRClassifier()
        self._frequency_provider = WordfreqFrequencyProvider()

    def analyze_text_use_case(self) -> AnalyzeTextUseCase:
        return AnalyzeTextUseCase(
            text_cleaner=self._text_cleaner,
            text_analyzer=self._text_analyzer,
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
        )

    def create_source_use_case(self, session: Session) -> CreateSourceUseCase:
        return CreateSourceUseCase(
            source_repo=SqlaSourceRepository(session),
        )

    def get_sources_use_case(self, session: Session) -> GetSourcesUseCase:
        return GetSourcesUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
        )

    def process_source_use_case(self, session: Session) -> ProcessSourceUseCase:
        return ProcessSourceUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            known_word_repo=SqlaKnownWordRepository(session),
            settings_repo=SqlaSettingsRepository(session),
            analyze_text_use_case=self.analyze_text_use_case(),
        )

    def get_candidates_use_case(self, session: Session) -> GetCandidatesUseCase:
        return GetCandidatesUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
        )

    def mark_candidate_use_case(self, session: Session) -> MarkCandidateUseCase:
        return MarkCandidateUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            known_word_repo=SqlaKnownWordRepository(session),
        )

    def manage_known_words_use_case(self, session: Session) -> ManageKnownWordsUseCase:
        return ManageKnownWordsUseCase(
            known_word_repo=SqlaKnownWordRepository(session),
        )

    def manage_settings_use_case(self, session: Session) -> ManageSettingsUseCase:
        return ManageSettingsUseCase(
            settings_repo=SqlaSettingsRepository(session),
        )
