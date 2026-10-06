from __future__ import annotations

import pytest
from backend.application.utils.anki_note_settings import AnkiFieldNames, AnkiNoteSettings
from backend.domain.ports.settings_repository import SettingsRepository

pytestmark = pytest.mark.unit


class _Settings(SettingsRepository):
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._values.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._values[key] = value


class TestAnkiNoteSettings:
    def test_defaults(self) -> None:
        settings = AnkiNoteSettings.read(_Settings({}))

        assert settings.recognition_note_type == "AnythingToAnkiType"
        assert settings.cloze_note_type == "AnythingToAnkiCloze"
        assert settings.fields.sentence == "Sentence"
        assert settings.fields.hint == "Hint"
        assert settings.fields.image == "Image"
        assert settings.fields.meaning_image == "MeaningImage"

    def test_user_names(self) -> None:
        settings = AnkiNoteSettings.read(_Settings({
            "anki_note_type": "Main",
            "anki_cloze_note_type": "Main Cloze",
            "anki_field_sentence": "Phrase",
            "anki_field_meaning_image": "Picture",
        }))

        assert settings.recognition_note_type == "Main"
        assert settings.cloze_note_type == "Main Cloze"
        assert settings.fields.sentence == "Phrase"
        assert settings.fields.meaning_image == "Picture"


class TestAnkiFieldNames:
    def test_both_note_types_share_the_fields_and_cloze_adds_the_hint(self) -> None:
        fields = AnkiFieldNames.read(_Settings({}))

        recognition = fields.recognition_fields()
        cloze = fields.cloze_fields()

        assert "Hint" not in recognition
        assert cloze == [recognition[0], "Hint", *recognition[1:]]
        assert recognition[0] == "Sentence"
        assert {"Image", "MeaningImage", "Audio"} <= set(recognition)

    def test_placeholders_carry_the_user_names(self) -> None:
        fields = AnkiFieldNames.read(_Settings({
            "anki_field_sentence": "Phrase", "anki_field_meaning_image": "Picture",
        }))

        placeholders = fields.placeholders()

        assert placeholders["FIELD_SENTENCE"] == "Phrase"
        assert placeholders["FIELD_MEANING_IMAGE"] == "Picture"
        assert placeholders["FIELD_HINT"] == "Hint"
