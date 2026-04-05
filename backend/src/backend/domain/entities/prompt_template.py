from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    """Prompt configuration for a named AI function."""

    id: int
    function_key: str  # code-level identifier, e.g. "generate_meaning"
    name: str          # human-readable name, e.g. "Definition generation"
    description: str   # what this prompt does
    system_prompt: str
    user_template: str  # Python format-string with {lemma}, {pos}, {context} placeholders
