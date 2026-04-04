from backend.domain.ports.anki_connector import AnkiConnector
from backend.domain.ports.candidate_repository import CandidateRepository
from backend.domain.ports.cefr_classifier import CEFRClassifier
from backend.domain.ports.dictionary_provider import DictionaryProvider
from backend.domain.ports.frequency_provider import FrequencyProvider
from backend.domain.ports.known_word_repository import KnownWordRepository
from backend.domain.ports.settings_repository import SettingsRepository
from backend.domain.ports.source_repository import SourceRepository
from backend.domain.ports.text_analyzer import TextAnalyzer
from backend.domain.ports.text_cleaner import TextCleaner

__all__ = [
    "AnkiConnector",
    "CandidateRepository",
    "CEFRClassifier",
    "DictionaryProvider",
    "FrequencyProvider",
    "KnownWordRepository",
    "SettingsRepository",
    "SourceRepository",
    "TextAnalyzer",
    "TextCleaner",
]
