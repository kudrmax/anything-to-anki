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
        self.settings_repo.get.side_effect = lambda key, default: {"cefr_level": "B1", "anki_deck_name": "VocabMiner"}.get(key, default)
        result = self.use_case.get_settings()
        assert result.cefr_level == "B1"
        assert result.anki_deck_name == "VocabMiner"

    def test_get_settings_default(self) -> None:
        self.settings_repo.get.return_value = None
        result = self.use_case.get_settings()
        assert result.cefr_level == "B1"
        assert result.anki_deck_name == "VocabMiner"

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

    def test_backward_compat_update_cefr_level(self) -> None:
        self.use_case.update_cefr_level("C1")
        self.settings_repo.set.assert_called_once_with("cefr_level", "C1")
