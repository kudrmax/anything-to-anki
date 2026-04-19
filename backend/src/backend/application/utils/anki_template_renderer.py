from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AnkiTemplateRenderer:
    """Reads Anki template files and substitutes %FIELD_X% placeholders."""

    templates_dir: Path
    _cache: dict[str, str] = field(
        default_factory=dict, init=False, repr=False, compare=False, hash=False,
    )

    def render_front(self, field_map: dict[str, str]) -> str:
        return self._substitute(self._read("front.html"), field_map)

    def render_back(self, field_map: dict[str, str]) -> str:
        return self._substitute(self._read("back.html"), field_map)

    def render_css(self) -> str:
        return self._read("style.css")

    def render_all(self, field_map: dict[str, str]) -> dict[str, str]:
        return {
            "front": self.render_front(field_map),
            "back": self.render_back(field_map),
            "css": self.render_css(),
        }

    def _read(self, filename: str) -> str:
        if filename not in self._cache:
            path = self.templates_dir / filename
            object.__setattr__(self, "_cache", {**self._cache, filename: path.read_text()})
        return self._cache[filename]

    @staticmethod
    def _substitute(template: str, field_map: dict[str, str]) -> str:
        result = template
        for placeholder, value in field_map.items():
            result = result.replace(f"%{placeholder}%", value)
        return result
