from unittest.mock import MagicMock

import pytest
from backend.application.dto.settings_dtos import UpdateSettingsRequest
from backend.application.use_cases.manage_settings import ManageSettingsUseCase


@pytest.mark.unit
class TestManageSettingsUseCase:
    def setup_method(self) -> None:
        self.settings_repo = MagicMock()
        self.use_case = ManageSettingsUseCase(settings_repo=self.settings_repo)

    def test_get_settings(self) -> None:
        self.settings_repo.get.side_effect = lambda key, default: {
            "cefr_level": "B1",
            "anki_deck_name": "Default",
        }.get(key, default)
        result = self.use_case.get_settings()
        assert result.cefr_level == "B1"
        assert result.anki_deck_name == "Default"

    def test_get_settings_default(self) -> None:
        self.settings_repo.get.return_value = None
        result = self.use_case.get_settings()
        assert result.cefr_level == "B1"
        assert result.anki_deck_name == "Default"
        assert result.ai_provider == "claude"
        assert result.ai_model == "sonnet"
        assert result.anki_note_type == "AnythingToAnkiType"
        assert result.anki_field_sentence == "Sentence"
        assert result.anki_field_target_word == "Target"
        assert result.anki_field_meaning == "Meaning"
        assert result.anki_field_ipa == "IPA"

    def test_update_cefr_level(self) -> None:
        self.settings_repo.get.return_value = None
        req = UpdateSettingsRequest(cefr_level="C1")
        self.use_case.update_settings(req)
        self.settings_repo.set.assert_any_call("cefr_level", "C1")

    def test_update_deck_name(self) -> None:
        self.settings_repo.get.return_value = None
        req = UpdateSettingsRequest(anki_deck_name="MyDeck")
        self.use_case.update_settings(req)
        self.settings_repo.set.assert_any_call("anki_deck_name", "MyDeck")

    def test_update_both_fields(self) -> None:
        self.settings_repo.get.return_value = None
        req = UpdateSettingsRequest(cefr_level="C2", anki_deck_name="Learning")
        self.use_case.update_settings(req)
        self.settings_repo.set.assert_any_call("cefr_level", "C2")
        self.settings_repo.set.assert_any_call("anki_deck_name", "Learning")

    def test_update_note_type(self) -> None:
        self.settings_repo.get.return_value = None
        req = UpdateSettingsRequest(anki_note_type="Basic")
        self.use_case.update_settings(req)
        self.settings_repo.set.assert_any_call("anki_note_type", "Basic")

    def test_update_field_mapping(self) -> None:
        self.settings_repo.get.return_value = None
        req = UpdateSettingsRequest(
            anki_field_sentence="Front",
            anki_field_target_word="Word",
            anki_field_meaning="Definition",
            anki_field_ipa="Pronunciation",
        )
        self.use_case.update_settings(req)
        self.settings_repo.set.assert_any_call("anki_field_sentence", "Front")
        self.settings_repo.set.assert_any_call("anki_field_target_word", "Word")
        self.settings_repo.set.assert_any_call("anki_field_meaning", "Definition")
        self.settings_repo.set.assert_any_call("anki_field_ipa", "Pronunciation")

    def test_backward_compat_update_cefr_level(self) -> None:
        self.use_case.update_cefr_level("C1")
        self.settings_repo.set.assert_called_once_with("cefr_level", "C1")

    def test_get_settings_includes_image_audio_defaults(self) -> None:
        self.settings_repo.get.return_value = None
        result = self.use_case.get_settings()
        assert result.anki_field_image == "Image"
        assert result.anki_field_audio == "Audio"

    def test_update_image_field(self) -> None:
        self.settings_repo.get.return_value = None
        req = UpdateSettingsRequest(anki_field_image="Picture")
        self.use_case.update_settings(req)
        self.settings_repo.set.assert_any_call("anki_field_image", "Picture")

    def test_update_audio_field(self) -> None:
        self.settings_repo.get.return_value = None
        req = UpdateSettingsRequest(anki_field_audio="Sound")
        self.use_case.update_settings(req)
        self.settings_repo.set.assert_any_call("anki_field_audio", "Sound")
