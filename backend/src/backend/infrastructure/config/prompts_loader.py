from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from backend.domain.exceptions import ConfigError
from backend.domain.value_objects.prompts_config import PromptsConfig

if TYPE_CHECKING:
    from pathlib import Path


_SECTION_ORDER: tuple[str, ...] = (
    "intro",
    "meaning",
    "translation",
    "synonyms",
    "ipa",
)


class PromptsLoader:
    """Loads AI prompt configuration from a YAML file and returns a PromptsConfig."""

    def load(self, path: Path) -> PromptsConfig:
        if not path.exists():
            raise ConfigError(f"Prompts config file not found: {path}")

        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise ConfigError(f"Failed to parse {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ConfigError(f"Prompts config root must be a mapping, got {type(raw).__name__}")

        generate = self._get_nested(raw, ["ai", "generate_meaning"], path)
        user_template = generate.get("user_template")
        if not isinstance(user_template, str):
            raise ConfigError(
                f"Missing or invalid 'ai.generate_meaning.user_template' in {path}"
            )

        system = generate.get("system")
        if not isinstance(system, dict):
            raise ConfigError(
                f"Missing or invalid 'ai.generate_meaning.system' in {path}"
            )

        sections: list[str] = []
        for key in _SECTION_ORDER:
            value = system.get(key)
            if not isinstance(value, str):
                raise ConfigError(
                    f"Missing or invalid 'ai.generate_meaning.system.{key}' in {path}"
                )
            sections.append(value)

        system_prompt = "\n\n".join(sections)

        return PromptsConfig(
            generate_meaning_user_template=user_template,
            generate_meaning_system=system_prompt,
        )

    def _get_nested(self, raw: dict[str, Any], keys: list[str], path: Path) -> dict[str, Any]:
        current: Any = raw
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                raise ConfigError(
                    f"Missing '{'.'.join(keys)}' in {path}"
                )
            current = current[key]
        if not isinstance(current, dict):
            raise ConfigError(
                f"'{'.'.join(keys)}' in {path} must be a mapping"
            )
        return current
