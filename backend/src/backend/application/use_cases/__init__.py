from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
from backend.application.use_cases.get_anki_status import GetAnkiStatusUseCase
from backend.application.use_cases.get_candidates import GetCandidatesUseCase
from backend.application.use_cases.get_export_cards import GetExportCardsUseCase
from backend.application.use_cases.get_sources import GetSourcesUseCase
from backend.application.use_cases.manage_known_words import ManageKnownWordsUseCase
from backend.application.use_cases.manage_settings import ManageSettingsUseCase
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase

__all__ = [
    "AnalyzeTextUseCase",
    "GetAnkiStatusUseCase",
    "GetCandidatesUseCase",
    "GetExportCardsUseCase",
    "GetSourcesUseCase",
    "ManageKnownWordsUseCase",
    "ManageSettingsUseCase",
    "DecidePhraseUseCase",
    "ProcessSourceUseCase",
    "SyncToAnkiUseCase",
]
