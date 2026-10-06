from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from backend.application.utils.anki_note_settings import AnkiFieldNames
from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer

pytestmark = pytest.mark.unit

REAL_TEMPLATES = Path(__file__).resolve().parents[4] / "anki-templates"

DEFAULT_FIELDS = AnkiFieldNames(
    sentence="Sentence", hint="Hint", target="Target", meaning="Meaning", ipa="IPA",
    translation="Translation", synonyms="Synonyms", examples="Examples",
    image="Image", meaning_image="MeaningImage", audio="Audio",
    audio_target_us="AudioTargetUS", audio_target_uk="AudioTargetUK", audio_tts="AudioTTS",
)


@pytest.fixture()
def templates_dir(tmp_path: Path) -> Path:
    (tmp_path / "front.html").write_text(
        '<div class="sentence">{{edit:%FIELD_SENTENCE%}}</div>\n'
        "{{#%FIELD_AUDIO%}}{{%FIELD_AUDIO%}}{{/%FIELD_AUDIO%}}"
    )
    (tmp_path / "back.html").write_text(
        "{{edit:%FIELD_TARGET%}} {{edit:%FIELD_MEANING%}}\n"
        "{{#%FIELD_IPA%}}{{%FIELD_IPA%}}{{/%FIELD_IPA%}}"
    )
    (tmp_path / "cloze-front.html").write_text(
        "{{cloze:%FIELD_SENTENCE%}} {{#%FIELD_HINT%}}{{%FIELD_HINT%}}{{/%FIELD_HINT%}}"
    )
    (tmp_path / "cloze-back.html").write_text(
        "{{cloze:%FIELD_SENTENCE%}} {{%FIELD_TARGET%}}"
    )
    (tmp_path / "style.css").write_text(".card { font-size: 18px; }")
    return tmp_path


class TestAnkiTemplateRenderer:
    def test_recognition_templates_get_the_field_names(self, templates_dir: Path) -> None:
        result = AnkiTemplateRenderer(templates_dir).render_recognition(DEFAULT_FIELDS)

        assert "{{edit:Sentence}}" in result.front
        assert "{{#Audio}}{{Audio}}{{/Audio}}" in result.front
        assert "{{edit:Target}} {{edit:Meaning}}" in result.back
        assert result.css == ".card { font-size: 18px; }"

    def test_user_names_replace_the_defaults(self, templates_dir: Path) -> None:
        fields = replace(DEFAULT_FIELDS, target="Word", ipa="Pronunciation")

        result = AnkiTemplateRenderer(templates_dir).render_recognition(fields)

        assert "{{edit:Word}}" in result.back
        assert "{{#Pronunciation}}{{Pronunciation}}{{/Pronunciation}}" in result.back

    def test_cloze_templates_share_the_field_names(self, templates_dir: Path) -> None:
        fields = replace(DEFAULT_FIELDS, sentence="Phrase")

        result = AnkiTemplateRenderer(templates_dir).render_cloze(fields)

        assert result.front == "{{cloze:Phrase}} {{#Hint}}{{Hint}}{{/Hint}}"
        assert result.back == "{{cloze:Phrase}} {{Target}}"
        assert result.css == ".card { font-size: 18px; }"

    def test_caches_template_files(self, templates_dir: Path) -> None:
        renderer = AnkiTemplateRenderer(templates_dir)
        first = renderer.render_recognition(DEFAULT_FIELDS)
        (templates_dir / "front.html").write_text("CHANGED")

        assert renderer.render_recognition(DEFAULT_FIELDS) == first


class TestRealTemplates:
    @pytest.mark.parametrize("kind", ["recognition", "cloze"])
    def test_every_placeholder_is_filled(self, kind: str) -> None:
        renderer = AnkiTemplateRenderer(REAL_TEMPLATES)
        result = getattr(renderer, f"render_{kind}")(DEFAULT_FIELDS)

        assert "%FIELD_" not in result.front + result.back

    @pytest.mark.parametrize("kind", ["recognition", "cloze"])
    def test_frame_on_the_front_meaning_image_only_on_the_back(self, kind: str) -> None:
        renderer = AnkiTemplateRenderer(REAL_TEMPLATES)
        result = getattr(renderer, f"render_{kind}")(DEFAULT_FIELDS)

        assert "{{Image}}" in result.front
        assert "{{MeaningImage}}" not in result.front
        assert "{{Image}}" in result.back
        assert "{{MeaningImage}}" in result.back
        assert result.back.index("{{MeaningImage}}") > result.back.index("Meaning}}")
        assert ".meaning-image" in result.css

    def test_cloze_uses_the_sentence_field_for_the_gap(self) -> None:
        result = AnkiTemplateRenderer(REAL_TEMPLATES).render_cloze(DEFAULT_FIELDS)

        assert "{{cloze:Sentence}}" in result.front
        assert "{{#Hint}}" in result.front
        assert "{{cloze:Sentence}}" in result.back
        assert "{{Target}}" in result.back
        assert ".cloze" in result.css
        assert ".hint" in result.css

    def test_cloze_front_does_not_speak_the_answer(self) -> None:
        result = AnkiTemplateRenderer(REAL_TEMPLATES).render_cloze(DEFAULT_FIELDS)

        assert "{{Audio}}" not in result.front
        assert "{{Audio}}" in result.back


class TestRealTemplatesAudio:
    def test_recognition_speaks_the_phrase_on_the_front_and_the_target_on_the_back(self) -> None:
        result = AnkiTemplateRenderer(REAL_TEMPLATES).render_recognition(DEFAULT_FIELDS)

        assert "{{AudioTTS}}" in result.front
        assert "{{AudioTargetUS}}" not in result.front
        assert "{{AudioTTS}}" in result.back
        assert "{{AudioTargetUS}}" in result.back
        assert "{{AudioTargetUK}}" in result.back

    def test_cloze_front_does_not_speak_the_phrase(self) -> None:
        result = AnkiTemplateRenderer(REAL_TEMPLATES).render_cloze(DEFAULT_FIELDS)

        assert "{{AudioTTS}}" not in result.front
        assert "{{AudioTargetUS}}" not in result.front
        assert "{{AudioTTS}}" in result.back
        assert "{{AudioTargetUK}}" in result.back
