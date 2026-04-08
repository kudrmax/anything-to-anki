from __future__ import annotations

from pathlib import Path

import pytest

from backend.domain.exceptions import ConfigError
from backend.infrastructure.config.prompts_loader import PromptsLoader


VALID_YAML = """
ai:
  generate_meaning:
    user_template: "Word: \\"{lemma}\\" ({pos})\\nContext: \\"{context}\\""
    system:
      intro: |
        You are a vocabulary assistant.
      meaning: |
        For the 'meaning' field, provide:
        - LINE 1: Definition.
      ipa: |
        For the 'ipa' field, provide the IPA transcription.
"""


@pytest.fixture
def valid_config_file(tmp_path: Path) -> Path:
    path = tmp_path / "prompts.yaml"
    path.write_text(VALID_YAML)
    return path


@pytest.mark.unit
def test_load_parses_user_template(valid_config_file: Path) -> None:
    cfg = PromptsLoader().load(valid_config_file)
    assert cfg.generate_meaning_user_template == (
        'Word: "{lemma}" ({pos})\nContext: "{context}"'
    )


@pytest.mark.unit
def test_load_joins_system_sections_in_order(valid_config_file: Path) -> None:
    cfg = PromptsLoader().load(valid_config_file)
    assert cfg.generate_meaning_system == (
        "You are a vocabulary assistant.\n"
        "\n\n"
        "For the 'meaning' field, provide:\n- LINE 1: Definition.\n"
        "\n\n"
        "For the 'ipa' field, provide the IPA transcription.\n"
    )


@pytest.mark.unit
def test_load_missing_file_raises_config_error(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(ConfigError) as exc_info:
        PromptsLoader().load(missing)
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.unit
def test_load_missing_user_template_raises(tmp_path: Path) -> None:
    path = tmp_path / "prompts.yaml"
    path.write_text(
        "ai:\n"
        "  generate_meaning:\n"
        "    system:\n"
        "      intro: x\n"
        "      meaning: y\n"
        "      ipa: z\n"
    )
    with pytest.raises(ConfigError) as exc_info:
        PromptsLoader().load(path)
    assert "user_template" in str(exc_info.value)


@pytest.mark.unit
def test_load_missing_system_section_raises(tmp_path: Path) -> None:
    path = tmp_path / "prompts.yaml"
    path.write_text(
        "ai:\n"
        "  generate_meaning:\n"
        "    user_template: 'x'\n"
        "    system:\n"
        "      intro: x\n"
        "      ipa: z\n"
    )
    with pytest.raises(ConfigError) as exc_info:
        PromptsLoader().load(path)
    assert "meaning" in str(exc_info.value)


@pytest.mark.unit
def test_load_invalid_yaml_raises(tmp_path: Path) -> None:
    path = tmp_path / "prompts.yaml"
    path.write_text("this: is: not valid: yaml: [")
    with pytest.raises(ConfigError):
        PromptsLoader().load(path)
