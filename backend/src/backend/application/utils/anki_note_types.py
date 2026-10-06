from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.application.utils.anki_note_settings import AnkiNoteSettings
    from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
    from backend.domain.ports.anki_connector import AnkiConnector


class AnkiNoteTypes:
    """Creates the two note types cards go to, with their fields and templates.

    A note type that already exists only gets the fields it lacks; its
    templates stay as the user left them.
    """

    def __init__(self, connector: AnkiConnector, renderer: AnkiTemplateRenderer) -> None:
        self._connector = connector
        self._renderer = renderer

    def ensure_recognition(self, settings: AnkiNoteSettings) -> None:
        templates = self._renderer.render_recognition(settings.fields)
        self._connector.ensure_note_type(
            settings.recognition_note_type,
            settings.fields.recognition_fields(),
            front_template=templates.front,
            back_template=templates.back,
            css=templates.css,
        )

    def ensure_cloze(self, settings: AnkiNoteSettings) -> None:
        templates = self._renderer.render_cloze(settings.fields)
        self._connector.ensure_note_type(
            settings.cloze_note_type,
            settings.fields.cloze_fields(),
            front_template=templates.front,
            back_template=templates.back,
            css=templates.css,
            is_cloze=True,
        )
