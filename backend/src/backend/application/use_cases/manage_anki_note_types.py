from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import NoteTypeCheckDTO
from backend.application.utils.anki_note_settings import AnkiNoteSettings
from backend.application.utils.anki_note_types import AnkiNoteTypes
from backend.domain.exceptions import AnkiNotAvailableError

if TYPE_CHECKING:
    from backend.application.utils.anki_note_types import NoteTypeKind
    from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
    from backend.domain.ports.anki_connector import AnkiConnector
    from backend.domain.ports.settings_repository import SettingsRepository


class ManageAnkiNoteTypesUseCase:
    """Shows how the note types the saved settings name stand in Anki, and fixes one on request.

    Fixing creates a note type that is not in Anki, or adds the fields the
    export fills to one that lacks them.
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

    def check(self) -> list[NoteTypeCheckDTO]:
        settings = self._settings()
        return [NoteTypeCheckDTO.of(check) for check in self._note_types().check_all(settings)]

    def fix(self, kind: NoteTypeKind) -> NoteTypeCheckDTO:
        settings = self._settings()
        note_types = self._note_types()
        note_types.ensure(kind, settings)
        return NoteTypeCheckDTO.of(note_types.check(kind, settings))

    def _settings(self) -> AnkiNoteSettings:
        if not self._connector.is_available():
            raise AnkiNotAvailableError()
        return AnkiNoteSettings.read(self._settings_repo)

    def _note_types(self) -> AnkiNoteTypes:
        return AnkiNoteTypes(self._connector, self._template_renderer)
