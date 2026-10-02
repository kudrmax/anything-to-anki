from __future__ import annotations

import pytest
from backend.domain.value_objects.prompts_config import PromptsConfig


@pytest.mark.unit
def test_prompts_config_is_frozen() -> None:
    cfg = PromptsConfig(
        generate_meaning_user_template='Word: "{lemma}"',
        generate_meaning_system="You are a vocabulary assistant.",
        generate_topic_targets_user_template="Request: {query}",
        generate_topic_targets_system="You help with topics.",
    )
    with pytest.raises(AttributeError):
        cfg.generate_meaning_user_template = "changed"  # type: ignore[misc]


@pytest.mark.unit
def test_prompts_config_stores_values() -> None:
    cfg = PromptsConfig(
        generate_meaning_user_template='Word: "{lemma}" ({pos})\nContext: "{context}"',
        generate_meaning_system="intro\n\nmeaning\n\nipa",
        generate_topic_targets_user_template="Request: {query}",
        generate_topic_targets_system="You help with topics.",
    )
    assert cfg.generate_meaning_user_template == 'Word: "{lemma}" ({pos})\nContext: "{context}"'
    assert cfg.generate_meaning_system == "intro\n\nmeaning\n\nipa"
