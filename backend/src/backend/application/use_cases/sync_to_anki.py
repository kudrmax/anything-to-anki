from __future__ import annotations

import re
from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import SyncResultDTO
from backend.domain.exceptions import AnkiNotAvailableError, AnkiSyncError
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.ports.anki_connector import AnkiConnector
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.dictionary_provider import DictionaryProvider
    from backend.domain.ports.settings_repository import SettingsRepository

_MODEL_NAME: str = "VocabMiner"
_MODEL_FIELDS: list[str] = ["Sentence", "Target", "Meaning", "API"]
_DEFAULT_DECK: str = "VocabMiner"


def _highlight(fragment: str, lemma: str) -> str:
    pattern = re.compile(r"\b(" + re.escape(lemma) + r")\b", re.IGNORECASE)
    result, count = pattern.subn(r"<b>\1</b>", fragment, count=1)
    return result if count else fragment


class SyncToAnkiUseCase:
    """Generates Anki cards for 'learn' candidates and pushes them via AnkiConnect."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        dictionary_provider: DictionaryProvider,
        anki_connector: AnkiConnector,
        settings_repo: SettingsRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._dictionary_provider = dictionary_provider
        self._connector = anki_connector
        self._settings_repo = settings_repo

    def execute(self, source_id: int) -> SyncResultDTO:
        deck_name = self._settings_repo.get("anki_deck_name", _DEFAULT_DECK) or _DEFAULT_DECK

        candidates = self._candidate_repo.get_by_source(source_id)
        learn_candidates = [c for c in candidates if c.status == CandidateStatus.LEARN]

        total = len(learn_candidates)
        if total == 0:
            return SyncResultDTO(total=0, added=0, skipped=0, errors=0)

        if not self._connector.is_available():
            raise AnkiNotAvailableError()

        self._connector.ensure_note_type(_MODEL_NAME, _MODEL_FIELDS)
        self._connector.ensure_deck(deck_name)

        added = 0
        skipped = 0
        errors = 0
        skipped_lemmas: list[str] = []
        error_lemmas: list[str] = []

        for candidate in learn_candidates:
            try:
                entry = self._dictionary_provider.get_entry(candidate.lemma, candidate.pos)
                sentence = _highlight(candidate.context_fragment, candidate.lemma)

                results = self._connector.add_notes(
                    deck_name=deck_name,
                    model_name=_MODEL_NAME,
                    notes=[{
                        "Sentence": sentence,
                        "Target": candidate.lemma,
                        "Meaning": entry.definition,
                        "API": entry.ipa or "",
                    }],
                )
                if results and results[0] is not None:
                    added += 1
                else:
                    errors += 1
                    error_lemmas.append(candidate.lemma)
            except AnkiNotAvailableError:
                raise
            except Exception as exc:  # noqa: BLE001
                if "duplicate" in str(exc).lower():
                    skipped += 1
                    skipped_lemmas.append(candidate.lemma)
                else:
                    errors += 1
                    error_lemmas.append(candidate.lemma)

        return SyncResultDTO(
            total=total, added=added, skipped=skipped, errors=errors,
            skipped_lemmas=skipped_lemmas, error_lemmas=error_lemmas,
        )
