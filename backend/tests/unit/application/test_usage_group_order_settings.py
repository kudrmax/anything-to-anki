import pytest
from backend.application.dto.settings_dtos import UpdateSettingsRequest
from backend.application.use_cases.manage_settings import ManageSettingsUseCase


class FakeSettingsRepo:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._data.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value


@pytest.mark.unit
class TestUsageGroupOrderSettings:
    def test_default_order(self) -> None:
        uc = ManageSettingsUseCase(FakeSettingsRepo())  # type: ignore[arg-type]
        settings = uc.get_settings()
        assert settings.usage_group_order == [
            "neutral", "informal", "formal", "specialized",
            "connotation", "old-fashioned", "offensive", "other",
        ]

    def test_update_order(self) -> None:
        repo = FakeSettingsRepo()
        uc = ManageSettingsUseCase(repo)  # type: ignore[arg-type]
        new_order = ["informal", "neutral", "formal", "specialized",
                     "connotation", "old-fashioned", "offensive", "other"]
        uc.update_settings(UpdateSettingsRequest(usage_group_order=new_order))
        settings = uc.get_settings()
        assert settings.usage_group_order == new_order

    def test_round_trip_preserves_order(self) -> None:
        repo = FakeSettingsRepo()
        uc = ManageSettingsUseCase(repo)  # type: ignore[arg-type]
        order = ["offensive", "other", "neutral", "informal",
                 "formal", "specialized", "connotation", "old-fashioned"]
        uc.update_settings(UpdateSettingsRequest(usage_group_order=order))
        assert uc.get_settings().usage_group_order == order
