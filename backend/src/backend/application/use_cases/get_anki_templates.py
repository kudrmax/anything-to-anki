from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import AnkiTemplatesDTO
from backend.application.utils.anki_note_settings import AnkiFieldNames

if TYPE_CHECKING:
    from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
    from backend.domain.ports.settings_repository import SettingsRepository


class GetAnkiTemplatesUseCase:
    """Card templates of both note types with the user's field names, to paste into Anki."""

    def __init__(
        self, settings_repo: SettingsRepository, template_renderer: AnkiTemplateRenderer,
    ) -> None:
        self._settings_repo = settings_repo
        self._template_renderer = template_renderer

    def execute(self) -> AnkiTemplatesDTO:
        fields = AnkiFieldNames.read(self._settings_repo)
        recognition = self._template_renderer.render_recognition(fields)
        cloze = self._template_renderer.render_cloze(fields)
        return AnkiTemplatesDTO(
            front=recognition.front,
            back=recognition.back,
            cloze_front=cloze.front,
            cloze_back=cloze.back,
            css=recognition.css,
        )
