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
        note_types = self._note_types()
        checks = [note_types.check_recognition(settings), note_types.check_cloze(settings)]
        return VerifyNoteTypesResponseDTO(
            valid=all(check.ok for check in checks),
            note_types=[NoteTypeCheckDTO.of(check) for check in checks],
        )

    def create(self) -> CreateNoteTypesResponseDTO:
        settings = self._settings()
        names = [settings.recognition_note_type, settings.cloze_note_type]
        created = [name for name in names if self._connector.get_model_field_names(name) is None]
        note_types = self._note_types()
        note_types.ensure_recognition(settings)
        note_types.ensure_cloze(settings)
        return CreateNoteTypesResponseDTO(created=created)

    def _settings(self) -> AnkiNoteSettings:
        if not self._connector.is_available():
            raise AnkiNotAvailableError()
        return AnkiNoteSettings.read(self._settings_repo)

    def _note_types(self) -> AnkiNoteTypes:
        return AnkiNoteTypes(self._connector, self._template_renderer)
