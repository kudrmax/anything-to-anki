from __future__ import annotations

from backend.application.use_cases.manage_settings import build_anki_field_map


class TestBuildAnkiFieldMap:
    def test_builds_map_from_defaults(self) -> None:
        settings = {
            "anki_field_sentence": "Sentence",
            "anki_field_target_word": "Target",
            "anki_field_meaning": "Meaning",
            "anki_field_ipa": "IPA",
            "anki_field_image": "Image",
            "anki_field_audio": "Audio",
            "anki_field_translation": "Translation",
            "anki_field_synonyms": "Synonyms",
            "anki_field_examples": "Examples",
        }
        result = build_anki_field_map(settings)
        assert result == {
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

    def test_builds_map_with_custom_names(self) -> None:
        settings = {
            "anki_field_sentence": "Front",
            "anki_field_target_word": "Word",
            "anki_field_meaning": "Def",
            "anki_field_ipa": "Pron",
            "anki_field_image": "Pic",
            "anki_field_audio": "Snd",
            "anki_field_translation": "RU",
            "anki_field_synonyms": "Syns",
            "anki_field_examples": "Ex",
        }
        result = build_anki_field_map(settings)
        assert result["FIELD_SENTENCE"] == "Front"
        assert result["FIELD_TARGET"] == "Word"
