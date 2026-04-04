from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.manage_settings import ManageSettingsUseCase


@pytest.mark.unit
class TestManageSettingsUseCase:
    def setup_method(self) -> None:
        self.settings_repo = MagicMock()
        self.use_case = ManageSettingsUseCase(settings_repo=self.settings_repo)

    def test_get_settings(self) -> None:
        self.settings_repo.get.return_value = "B1"
        result = self.use_case.get_settings()
        assert result.cefr_level == "B1"

    def test_get_settings_default(self) -> None:
        self.settings_repo.get.return_value = None
        result = self.use_case.get_settings()
        assert result.cefr_level == "B1"

    def test_update_settings(self) -> None:
        self.use_case.update_cefr_level("C1")
        self.settings_repo.set.assert_called_once_with("cefr_level", "C1")
