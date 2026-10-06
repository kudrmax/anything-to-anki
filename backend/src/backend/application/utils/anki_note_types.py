from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.utils.anki_note_settings import (
    DEFAULT_CLOZE_NOTE_TYPE,
    DEFAULT_RECOGNITION_NOTE_TYPE,
)

if TYPE_CHECKING:
    from backend.application.utils.anki_note_settings import AnkiNoteSettings
    from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
    from backend.domain.ports.anki_connector import AnkiConnector


@dataclass(frozen=True)
class NoteTypeCheck:
    """Whether a note type is in Anki and which fields the export fills it still lacks.

    Anki drops a field the note type does not have without a word, so a note
    type that misses a field loses that part of every card.
    """

    note_type: str
    exists: bool
    missing_fields: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.exists and not self.missing_fields


class AnkiNoteTypes:
    """Creates and checks the two note types cards go to.

    A note type that already exists only gets the fields it lacks; its
    templates stay as the user left them. The export creates the app's own
    note types by itself; a user's own note type must be fixed by the user.
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

    def check_recognition(self, settings: AnkiNoteSettings) -> NoteTypeCheck:
        return self._check(settings.recognition_note_type, settings.fields.recognition_fields())

    def check_cloze(self, settings: AnkiNoteSettings) -> NoteTypeCheck:
        return self._check(settings.cloze_note_type, settings.fields.cloze_fields())

    def problems(self, settings: AnkiNoteSettings) -> list[NoteTypeCheck]:
        """User's own note types that would lose parts of the cards on export."""
        checks = []
        if settings.recognition_note_type != DEFAULT_RECOGNITION_NOTE_TYPE:
            checks.append(self.check_recognition(settings))
        if settings.cloze_note_type != DEFAULT_CLOZE_NOTE_TYPE:
            checks.append(self.check_cloze(settings))
        return [check for check in checks if not check.ok]

    def _check(self, note_type: str, required: list[str]) -> NoteTypeCheck:
        available = self._connector.get_model_field_names(note_type)
        if available is None:
            return NoteTypeCheck(note_type, exists=False, missing_fields=tuple(required))
        missing = tuple(name for name in required if name not in available)
        return NoteTypeCheck(note_type, exists=True, missing_fields=missing)
