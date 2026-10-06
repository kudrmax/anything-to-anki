from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from backend.application.utils.anki_note_settings import (
    DEFAULT_CLOZE_NOTE_TYPE,
    DEFAULT_RECOGNITION_NOTE_TYPE,
)

if TYPE_CHECKING:
    from backend.application.utils.anki_note_settings import AnkiNoteSettings
    from backend.application.utils.anki_template_renderer import (
        AnkiTemplateRenderer,
        NoteTemplates,
    )
    from backend.domain.ports.anki_connector import AnkiConnector


class NoteTypeKind(StrEnum):
    RECOGNITION = "recognition"
    CLOZE = "cloze"


_APP_NOTE_TYPES: dict[NoteTypeKind, str] = {
    NoteTypeKind.RECOGNITION: DEFAULT_RECOGNITION_NOTE_TYPE,
    NoteTypeKind.CLOZE: DEFAULT_CLOZE_NOTE_TYPE,
}


class NoteTypeFix(StrEnum):
    """What makes a note type able to take the cards."""

    CREATE = "create"
    ADD_FIELDS = "add_fields"


@dataclass(frozen=True)
class NoteTypeCheck:
    """Whether a note type is in Anki and which fields the export fills it still lacks.

    Anki drops a field the note type does not have without a word, so a note
    type that misses a field loses that part of every card.
    """

    kind: NoteTypeKind
    note_type: str
    exists: bool
    missing_fields: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.fix is None

    @property
    def fix(self) -> NoteTypeFix | None:
        if not self.exists:
            return NoteTypeFix.CREATE
        if self.missing_fields:
            return NoteTypeFix.ADD_FIELDS
        return None


class AnkiNoteTypes:
    """Creates and checks the two note types cards go to.

    A note type that already exists only gets the fields it lacks; its
    templates stay as the user left them. The export creates the app's own
    note types by itself; a user's own note type is fixed only on request.
    """

    def __init__(self, connector: AnkiConnector, renderer: AnkiTemplateRenderer) -> None:
        self._connector = connector
        self._renderer = renderer

    def ensure(self, kind: NoteTypeKind, settings: AnkiNoteSettings) -> None:
        templates = self._templates(kind, settings)
        self._connector.ensure_note_type(
            _name(kind, settings),
            _fields(kind, settings),
            front_template=templates.front,
            back_template=templates.back,
            css=templates.css,
            is_cloze=kind is NoteTypeKind.CLOZE,
        )

    def check(self, kind: NoteTypeKind, settings: AnkiNoteSettings) -> NoteTypeCheck:
        note_type = _name(kind, settings)
        required = _fields(kind, settings)
        available = self._connector.get_model_field_names(note_type)
        if available is None:
            return NoteTypeCheck(kind, note_type, exists=False, missing_fields=tuple(required))
        missing = tuple(name for name in required if name not in available)
        return NoteTypeCheck(kind, note_type, exists=True, missing_fields=missing)

    def check_all(self, settings: AnkiNoteSettings) -> list[NoteTypeCheck]:
        return [self.check(kind, settings) for kind in NoteTypeKind]

    def problems(self, settings: AnkiNoteSettings) -> list[NoteTypeCheck]:
        """User's own note types that would lose parts of the cards on export."""
        return [
            check for check in self.check_all(settings)
            if not check.ok and not is_app_note_type(check.kind, settings)
        ]

    def _templates(self, kind: NoteTypeKind, settings: AnkiNoteSettings) -> NoteTemplates:
        if kind is NoteTypeKind.CLOZE:
            return self._renderer.render_cloze(settings.fields)
        return self._renderer.render_recognition(settings.fields)


def is_app_note_type(kind: NoteTypeKind, settings: AnkiNoteSettings) -> bool:
    """The app's own note type, which the export creates and completes by itself."""
    return _name(kind, settings) == _APP_NOTE_TYPES[kind]


def _name(kind: NoteTypeKind, settings: AnkiNoteSettings) -> str:
    if kind is NoteTypeKind.CLOZE:
        return settings.cloze_note_type
    return settings.recognition_note_type


def _fields(kind: NoteTypeKind, settings: AnkiNoteSettings) -> list[str]:
    if kind is NoteTypeKind.CLOZE:
        return settings.fields.cloze_fields()
    return settings.fields.recognition_fields()
