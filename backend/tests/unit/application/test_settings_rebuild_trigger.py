from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from backend.application.constants import FREQUENT_WORD_THRESHOLD_SETTING
from backend.application.dto.settings_dtos import UpdateSettingsRequest
from backend.application.use_cases.manage_settings import ManageSettingsUseCase
from backend.domain.ports.sources_rebuild_launcher import SourcesRebuildLauncher
from backend.domain.ports.unit_of_work import UnitOfWork

from tests.candidate_sorter_support import threshold_resolver


class FakeSettingsRepo:
    def __init__(self, events: list[str]) -> None:
        self._data: dict[str, str] = {}
        self._events = events

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._data.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._events.append(f"set {key}")
        self._data[key] = value


class RecordingLauncher(SourcesRebuildLauncher):
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def rebuild_all(self) -> None:
        self._events.append("rebuild_all")


class RecordingUnitOfWork(UnitOfWork):
    def __init__(self, events: list[str]) -> None:
        self._events = events

    @contextmanager
    def write(self) -> Iterator[None]:
        self._events.append("write")
        yield
        self._events.append("committed")


@pytest.fixture
def events() -> list[str]:
    return []


@pytest.fixture
def use_case(events: list[str]) -> ManageSettingsUseCase:
    repo = FakeSettingsRepo(events)
    return ManageSettingsUseCase(
        repo,  # type: ignore[arg-type]
        threshold_resolver(repo),  # type: ignore[arg-type]
        RecordingUnitOfWork(events),
        RecordingLauncher(events),
    )


@pytest.mark.unit
def test_a_new_level_rebuilds_once_after_the_commit(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(UpdateSettingsRequest(cefr_level="C1"))
    assert events == ["write", "set cefr_level", "committed", "rebuild_all"]


@pytest.mark.unit
def test_update_cefr_level_rebuilds_when_it_changes(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_cefr_level("C2")
    assert events == ["write", "set cefr_level", "committed", "rebuild_all"]


@pytest.mark.unit
@pytest.mark.parametrize("threshold", ["4.0", "5.5", "off"])
def test_a_new_threshold_rebuilds_once(
    use_case: ManageSettingsUseCase, events: list[str], threshold: str,
) -> None:
    use_case.update_settings(UpdateSettingsRequest(frequent_word_threshold=threshold))
    assert events == [
        "write", f"set {FREQUENT_WORD_THRESHOLD_SETTING}", "committed", "rebuild_all",
    ]


@pytest.mark.unit
def test_switching_back_to_auto_rebuilds(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(UpdateSettingsRequest(frequent_word_threshold="5.0"))
    events.clear()
    use_case.update_settings(UpdateSettingsRequest(frequent_word_threshold="auto"))
    assert events == [
        "write", f"set {FREQUENT_WORD_THRESHOLD_SETTING}", "committed", "rebuild_all",
    ]


@pytest.mark.unit
def test_both_changing_together_rebuilds_once(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(
        UpdateSettingsRequest(cefr_level="A2", frequent_word_threshold="4.0"),
    )
    assert events.count("rebuild_all") == 1


@pytest.mark.unit
def test_the_same_values_rebuild_nothing(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(
        UpdateSettingsRequest(cefr_level="C1", frequent_word_threshold="5.0"),
    )
    events.clear()
    use_case.update_settings(
        UpdateSettingsRequest(cefr_level="C1", frequent_word_threshold="5.0"),
    )
    use_case.update_cefr_level("C1")
    assert "rebuild_all" not in events


@pytest.mark.unit
def test_the_default_value_written_explicitly_rebuilds_nothing(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(
        UpdateSettingsRequest(cefr_level="B1", frequent_word_threshold="auto"),
    )
    assert "rebuild_all" not in events


@pytest.mark.unit
def test_an_unrelated_setting_rebuilds_nothing(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(
        UpdateSettingsRequest(anki_deck_name="Other", tts_speed=1.2, enable_definitions=False),
    )
    assert "rebuild_all" not in events


@pytest.mark.unit
def test_an_unrelated_setting_is_written_inside_one_write(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(UpdateSettingsRequest(anki_deck_name="Other"))
    assert events == ["write", "set anki_deck_name", "committed"]
