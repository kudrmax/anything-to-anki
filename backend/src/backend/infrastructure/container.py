from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
from backend.application.use_cases.generate_meaning import GenerateMeaningUseCase
from backend.application.use_cases.create_source import CreateSourceUseCase
from backend.application.use_cases.delete_source import DeleteSourceUseCase
from backend.application.use_cases.get_anki_status import GetAnkiStatusUseCase
from backend.application.use_cases.get_candidates import GetCandidatesUseCase
from backend.application.use_cases.get_source_cards import GetSourceCardsUseCase
from backend.application.use_cases.get_sources import GetSourcesUseCase
from backend.application.use_cases.get_stats import GetStatsUseCase
from backend.application.use_cases.manage_known_words import ManageKnownWordsUseCase
from backend.application.use_cases.manage_settings import ManageSettingsUseCase
from backend.application.use_cases.mark_candidate import MarkCandidateUseCase
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.infrastructure.adapters.anki_connect_connector import AnkiConnectConnector
from backend.infrastructure.adapters.ai_model_mapping import model_id_for
from backend.infrastructure.adapters.http_ai_service import HttpAIService
from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
from backend.infrastructure.adapters.cached_dictionary_api_provider import (
    CachedDictionaryApiProvider,
)
from backend.infrastructure.adapters.cefrpy_classifier import CefrpyCEFRClassifier
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer
from backend.infrastructure.adapters.json_phrasal_verb_dictionary import (
    JsonPhrasalVerbDictionary,
)
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
        self._anki_connector = AnkiConnectConnector()
        self._phrasal_verb_dictionary = JsonPhrasalVerbDictionary()

    def analyze_text_use_case(self) -> AnalyzeTextUseCase:
        return AnalyzeTextUseCase(
            text_cleaner=self._text_cleaner,
            text_analyzer=self._text_analyzer,
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            phrasal_verb_detector=PhrasalVerbDetector(self._phrasal_verb_dictionary),
        )

    def create_source_use_case(self, session: Session) -> CreateSourceUseCase:
        return CreateSourceUseCase(
            source_repo=SqlaSourceRepository(session),
        )

    def delete_source_use_case(self, session: Session) -> DeleteSourceUseCase:
        return DeleteSourceUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
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

    def get_anki_status_use_case(self) -> GetAnkiStatusUseCase:
        return GetAnkiStatusUseCase(connector=self._anki_connector)

    def sync_to_anki_use_case(self, session: Session) -> SyncToAnkiUseCase:
        return SyncToAnkiUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            dictionary_provider=CachedDictionaryApiProvider(session),
            anki_connector=self._anki_connector,
            settings_repo=SqlaSettingsRepository(session),
        )

    def get_source_cards_use_case(self, session: Session) -> GetSourceCardsUseCase:
        return GetSourceCardsUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            dictionary_provider=CachedDictionaryApiProvider(session),
        )

    def generate_meaning_use_case(self, session: Session) -> GenerateMeaningUseCase:
        import os

        settings_repo = SqlaSettingsRepository(session)
        ai_model_key = settings_repo.get("ai_model", "sonnet") or "sonnet"
        ai_proxy_url = os.environ["AI_PROXY_URL"]
        ai_service = HttpAIService(url=ai_proxy_url, model=model_id_for(ai_model_key))
        return GenerateMeaningUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            ai_service=ai_service,
        )

    def get_stats_use_case(self, session: Session) -> GetStatsUseCase:
        return GetStatsUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            known_word_repo=SqlaKnownWordRepository(session),
        )

    def anki_connector(self) -> AnkiConnectConnector:
        return self._anki_connector
