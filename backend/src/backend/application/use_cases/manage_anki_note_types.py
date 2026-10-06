from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import (
    CreateNoteTypesResponseDTO,
    NoteTypeCheckDTO,
    VerifyNoteTypesResponseDTO,
)
from backend.application.utils.anki_note_settings import AnkiNoteSettings
from backend.application.utils.anki_note_types import AnkiNoteTypes
from backend.domain.exceptions import AnkiNotAvailableError

if TYPE_CHECKING:
    from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
    from backend.domain.ports.anki_connector import AnkiConnector
    from backend.domain.ports.settings_repository import SettingsRepository


class ManageAnkiNoteTypesUseCase:
    """Checks and creates in Anki the note types the saved settings name.

    Both types are checked against the fields the export fills in them.
    """

    def __init__(
        self,
        connector: AnkiConnector,
        settings_repo: SettingsRepository,
        template_renderer: AnkiTemplateRenderer,
    ) -> None:
        self._connector = connector
        self._settings_repo = settings_repo
        self._template_renderer = template_renderer

    def verify(self) -> VerifyNoteTypesResponseDTO:
        settings = self._settings()
        checks = [
            self._check(settings.recognition_note_type, settings.fields.recognition_fields()),
            self._check(settings.cloze_note_type, settings.fields.cloze_fields()),
        ]
        valid = all(check.exists and not check.missing_fields for check in checks)
        return VerifyNoteTypesResponseDTO(valid=valid, note_types=checks)

    def create(self) -> CreateNoteTypesResponseDTO:
        settings = self._settings()
        names = [settings.recognition_note_type, settings.cloze_note_type]
        created = [name for name in names if self._connector.get_model_field_names(name) is None]
        note_types = AnkiNoteTypes(self._connector, self._template_renderer)
        note_types.ensure_recognition(settings)
        note_types.ensure_cloze(settings)
        return CreateNoteTypesResponseDTO(created=created)

    def _settings(self) -> AnkiNoteSettings:
        if not self._connector.is_available():
            raise AnkiNotAvailableError()
        return AnkiNoteSettings.read(self._settings_repo)

    def _check(self, note_type: str, required: list[str]) -> NoteTypeCheckDTO:
        available = self._connector.get_model_field_names(note_type)
        if available is None:
            return NoteTypeCheckDTO(note_type=note_type, exists=False, missing_fields=required)
        missing = [name for name in required if name not in available]
        return NoteTypeCheckDTO(note_type=note_type, exists=True, missing_fields=missing)
