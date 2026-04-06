from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import SyncResultDTO
from backend.application.utils.highlight import highlight_all_forms
from backend.domain.exceptions import AnkiNotAvailableError, AnkiSyncError
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.ports.anki_connector import AnkiConnector
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.settings_repository import SettingsRepository

_DEFAULT_NOTE_TYPE: str = "AnythingToAnkiType"
_DEFAULT_DECK: str = "Default"
_DEFAULT_FIELD_SENTENCE: str = "Sentence"
_DEFAULT_FIELD_TARGET: str = "Target"
_DEFAULT_FIELD_MEANING: str = "Meaning"
_DEFAULT_FIELD_IPA: str = "IPA"


class SyncToAnkiUseCase:
    """Generates Anki cards for 'learn' candidates and pushes them via AnkiConnect."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        anki_connector: AnkiConnector,
        settings_repo: SettingsRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._connector = anki_connector
        self._settings_repo = settings_repo

    def execute(self, source_id: int) -> SyncResultDTO:
        deck_name = self._settings_repo.get("anki_deck_name", _DEFAULT_DECK) or _DEFAULT_DECK
        note_type = self._settings_repo.get("anki_note_type", _DEFAULT_NOTE_TYPE) or _DEFAULT_NOTE_TYPE
        field_sentence = self._settings_repo.get("anki_field_sentence", _DEFAULT_FIELD_SENTENCE) or _DEFAULT_FIELD_SENTENCE
        field_target = self._settings_repo.get("anki_field_target_word", _DEFAULT_FIELD_TARGET) or _DEFAULT_FIELD_TARGET
        field_meaning = self._settings_repo.get("anki_field_meaning", _DEFAULT_FIELD_MEANING) or _DEFAULT_FIELD_MEANING
        field_ipa = self._settings_repo.get("anki_field_ipa", _DEFAULT_FIELD_IPA) or _DEFAULT_FIELD_IPA

        candidates = self._candidate_repo.get_by_source(source_id)
        learn_candidates = [c for c in candidates if c.status == CandidateStatus.LEARN]

        total = len(learn_candidates)
        if total == 0:
            return SyncResultDTO(total=0, added=0, skipped=0, errors=0)

        if not self._connector.is_available():
            raise AnkiNotAvailableError()

        active_fields = [f for f in [field_sentence, field_target, field_meaning, field_ipa] if f]
        if note_type == _DEFAULT_NOTE_TYPE:
            self._connector.ensure_note_type(note_type, active_fields)
        self._connector.ensure_deck(deck_name)

        added = 0
        skipped = 0
        errors = 0
        skipped_lemmas: list[str] = []
        error_lemmas: list[str] = []

        for candidate in learn_candidates:
            try:
                sentence = highlight_all_forms(
                    candidate.context_fragment,
                    candidate.lemma,
                    candidate.surface_form,
                )
                meaning = (
                    highlight_all_forms(
                        candidate.meaning,
                        candidate.lemma,
                        candidate.surface_form,
                    )
                    if candidate.meaning
                    else ""
                )

                note: dict[str, str] = {}
                if field_sentence:
                    note[field_sentence] = sentence
                if field_target:
                    note[field_target] = candidate.lemma
                if field_meaning:
                    note[field_meaning] = meaning
                if field_ipa:
                    note[field_ipa] = candidate.ipa or ""

                results = self._connector.add_notes(
                    deck_name=deck_name,
                    model_name=note_type,
                    notes=[note],
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
