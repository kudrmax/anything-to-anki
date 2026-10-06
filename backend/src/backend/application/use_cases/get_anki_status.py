from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import AnkiStatusDTO, NoteTypeCheckDTO
from backend.application.utils.anki_note_settings import AnkiNoteSettings
from backend.application.utils.anki_note_types import AnkiNoteTypes

if TYPE_CHECKING:
    from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
    from backend.domain.ports.anki_connector import AnkiConnector
    from backend.domain.ports.settings_repository import SettingsRepository


class GetAnkiStatusUseCase:
    """Checks whether AnkiConnect is reachable and whether the note types can take the cards."""

    def __init__(
        self,
        connector: AnkiConnector,
        settings_repo: SettingsRepository,
        template_renderer: AnkiTemplateRenderer,
    ) -> None:
        self._connector = connector
        self._settings_repo = settings_repo
        self._template_renderer = template_renderer

    def execute(self) -> AnkiStatusDTO:
        if not self._connector.is_available():
            return AnkiStatusDTO(available=False)
        settings = AnkiNoteSettings.read(self._settings_repo)
        problems = AnkiNoteTypes(self._connector, self._template_renderer).problems(settings)
        return AnkiStatusDTO(
            available=True,
            note_type_problems=[NoteTypeCheckDTO.of(problem) for problem in problems],
        )
