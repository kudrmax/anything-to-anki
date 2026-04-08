from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptsConfig:
    """Immutable container for AI prompt configuration loaded from YAML."""

    generate_meaning_user_template: str
    generate_meaning_system: str
