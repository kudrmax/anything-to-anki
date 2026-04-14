from backend.domain.ports.ai_service import AIService
from backend.domain.ports.anki_connector import AnkiConnector
from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
from backend.domain.ports.candidate_repository import CandidateRepository
from backend.domain.ports.cefr_classifier import CEFRClassifier
from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.ports.frequency_provider import FrequencyProvider
from backend.domain.ports.known_word_repository import KnownWordRepository
from backend.domain.ports.settings_repository import SettingsRepository
from backend.domain.ports.source_repository import SourceRepository
from backend.domain.ports.text_analyzer import TextAnalyzer
from backend.domain.ports.text_cleaner import TextCleaner

__all__ = [
    "AIService",
    "AnkiConnector",
    "CandidateMeaningRepository",
    "CandidateMediaRepository",
    "CandidateRepository",
    "CEFRClassifier",
    "CEFRSource",
    "FrequencyProvider",
    "KnownWordRepository",
    "SettingsRepository",
    "SourceRepository",
    "TextAnalyzer",
    "TextCleaner",
]
