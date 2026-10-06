from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from backend.application.utils.anki_note_settings import AnkiFieldNames


@dataclass(frozen=True)
class NoteTemplates:
    """Card templates and styling of one note type."""

    front: str
    back: str
    css: str


@dataclass(frozen=True)
class AnkiTemplateRenderer:
    """Reads Anki template files and substitutes %FIELD_X% placeholders with field names.

    Both note types share the field names and the styling; they differ only
    in their front and back templates.
    """

    templates_dir: Path
    _cache: dict[str, str] = field(
        default_factory=dict, init=False, repr=False, compare=False, hash=False,
    )

    def render_recognition(self, fields: AnkiFieldNames) -> NoteTemplates:
        return self._render("front.html", "back.html", fields)

    def render_cloze(self, fields: AnkiFieldNames) -> NoteTemplates:
        return self._render("cloze-front.html", "cloze-back.html", fields)

    def _render(self, front: str, back: str, fields: AnkiFieldNames) -> NoteTemplates:
        placeholders = fields.placeholders()
        return NoteTemplates(
            front=_substitute(self._read(front), placeholders),
            back=_substitute(self._read(back), placeholders),
            css=self._read("style.css"),
        )

    def _read(self, filename: str) -> str:
        if filename not in self._cache:
            path = self.templates_dir / filename
            object.__setattr__(self, "_cache", {**self._cache, filename: path.read_text()})
        return self._cache[filename]


def _substitute(template: str, placeholders: dict[str, str]) -> str:
    result = template
    for placeholder, value in placeholders.items():
        result = result.replace(f"%{placeholder}%", value)
    return result
