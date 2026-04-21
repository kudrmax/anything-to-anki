from __future__ import annotations

from pathlib import Path

import pytest
from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer


@pytest.fixture()
def templates_dir(tmp_path: Path) -> Path:
    front = tmp_path / "front.html"
    front.write_text(
        '<div class="sentence">{{edit:%FIELD_SENTENCE%}}</div>\n'
        "{{#%FIELD_AUDIO%}}{{%FIELD_AUDIO%}}{{/%FIELD_AUDIO%}}"
    )
    back = tmp_path / "back.html"
    back.write_text(
        "{{edit:%FIELD_TARGET%}} {{edit:%FIELD_MEANING%}}\n"
        "{{#%FIELD_IPA%}}{{%FIELD_IPA%}}{{/%FIELD_IPA%}}\n"
        "{{#%FIELD_IMAGE%}}{{%FIELD_IMAGE%}}{{/%FIELD_IMAGE%}}\n"
        "{{#%FIELD_TRANSLATION%}}{{%FIELD_TRANSLATION%}}{{/%FIELD_TRANSLATION%}}\n"
        "{{#%FIELD_SYNONYMS%}}{{%FIELD_SYNONYMS%}}{{/%FIELD_SYNONYMS%}}\n"
        "{{#%FIELD_EXAMPLES%}}{{%FIELD_EXAMPLES%}}{{/%FIELD_EXAMPLES%}}"
    )
    style = tmp_path / "style.css"
    style.write_text(".card { font-size: 18px; }")
    return tmp_path


def _default_field_map() -> dict[str, str]:
    return {
        "FIELD_SENTENCE": "Sentence",
        "FIELD_TARGET": "Target",
        "FIELD_MEANING": "Meaning",
        "FIELD_IPA": "IPA",
        "FIELD_IMAGE": "Image",
        "FIELD_AUDIO": "Audio",
        "FIELD_TRANSLATION": "Translation",
        "FIELD_SYNONYMS": "Synonyms",
        "FIELD_EXAMPLES": "Examples",
    }


class TestAnkiTemplateRenderer:
    def test_renders_front_with_default_fields(self, templates_dir: Path) -> None:
        renderer = AnkiTemplateRenderer(templates_dir)
        result = renderer.render_front(_default_field_map())
        assert "{{edit:Sentence}}" in result
        assert "{{#Audio}}{{Audio}}{{/Audio}}" in result
        assert "%FIELD_" not in result

    def test_renders_back_with_custom_fields(self, templates_dir: Path) -> None:
        renderer = AnkiTemplateRenderer(templates_dir)
        field_map = {
            "FIELD_SENTENCE": "Front",
            "FIELD_TARGET": "Word",
            "FIELD_MEANING": "Definition",
            "FIELD_IPA": "Pronunciation",
            "FIELD_IMAGE": "Picture",
            "FIELD_AUDIO": "Sound",
            "FIELD_TRANSLATION": "RU",
            "FIELD_SYNONYMS": "Syns",
            "FIELD_EXAMPLES": "Ex",
        }
        result = renderer.render_back(field_map)
        assert "{{edit:Word}}" in result
        assert "{{edit:Definition}}" in result
        assert "{{#Pronunciation}}{{Pronunciation}}{{/Pronunciation}}" in result
        assert "%FIELD_" not in result

    def test_renders_css_unchanged(self, templates_dir: Path) -> None:
        renderer = AnkiTemplateRenderer(templates_dir)
        result = renderer.render_css()
        assert result == ".card { font-size: 18px; }"

    def test_render_all_returns_three_parts(self, templates_dir: Path) -> None:
        renderer = AnkiTemplateRenderer(templates_dir)
        result = renderer.render_all(_default_field_map())
        assert "front" in result
        assert "back" in result
        assert "css" in result
        assert "%FIELD_" not in result["front"]
        assert "%FIELD_" not in result["back"]

    def test_caches_template_files(self, templates_dir: Path) -> None:
        renderer = AnkiTemplateRenderer(templates_dir)
        result1 = renderer.render_front(_default_field_map())
        (templates_dir / "front.html").write_text("CHANGED")
        result2 = renderer.render_front(_default_field_map())
        assert result1 == result2
