"""A settings update that changes what the analysis depends on is a level change; any other
is written at once, inside one write."""
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from backend.application.constants import FREQUENT_WORD_THRESHOLD_SETTING
from backend.application.dto.settings_dtos import UpdateSettingsRequest
from backend.application.use_cases.manage_settings import ManageSettingsUseCase
from backend.application.utils.level_change_launcher import LevelChangeLauncher
from backend.domain.ports.unit_of_work import UnitOfWork

LEVEL_CHANGE = "level_change"


class FakeSettingsRepo:
    def __init__(self, events: list[str]) -> None:
        self.data: dict[str, str] = {}
        self._events = events

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.data.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._events.append(f"set {key}")
        self.data[key] = value


class RecordingLauncher(LevelChangeLauncher):
    """Records the start and applies the request, as the finished change would."""

    def __init__(self, events: list[str], repo: FakeSettingsRepo) -> None:
        self._events = events
        self._repo = repo

    def start(self, request: UpdateSettingsRequest) -> None:
        self._events.append(LEVEL_CHANGE)
        for key, value in request.model_dump(exclude_none=True).items():
            self._repo.data[key] = str(value)


class RecordingUnitOfWork(UnitOfWork):
    def __init__(self, events: list[str]) -> None:
        self._events = events

    @contextmanager
    def write(self) -> Iterator[None]:
        self._events.append("write")
        yield
        self._events.append("committed")

    @contextmanager
    def read(self) -> Iterator[None]:
        yield


@pytest.fixture
def events() -> list[str]:
    return []


@pytest.fixture
def use_case(events: list[str]) -> ManageSettingsUseCase:
    repo = FakeSettingsRepo(events)
    return ManageSettingsUseCase(
        repo,  # type: ignore[arg-type]
        RecordingUnitOfWork(events),
        RecordingLauncher(events, repo),
    )


@pytest.mark.unit
def test_a_new_level_is_a_level_change_and_nothing_is_written_here(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(UpdateSettingsRequest(cefr_level="C1"))
    assert events == [LEVEL_CHANGE]


@pytest.mark.unit
@pytest.mark.parametrize("threshold", ["4.0", "4.5", "5.5"])
def test_a_new_threshold_is_a_level_change(
    use_case: ManageSettingsUseCase, events: list[str], threshold: str,
) -> None:
    use_case.update_settings(UpdateSettingsRequest(frequent_word_threshold=threshold))
    assert events == [LEVEL_CHANGE]


@pytest.mark.unit
def test_switching_back_to_off_is_a_level_change(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(UpdateSettingsRequest(frequent_word_threshold="5.0"))
    events.clear()
    use_case.update_settings(UpdateSettingsRequest(frequent_word_threshold="off"))
    assert events == [LEVEL_CHANGE]


@pytest.mark.unit
def test_both_changing_together_is_one_level_change(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(
        UpdateSettingsRequest(cefr_level="A2", frequent_word_threshold="4.0"),
    )
    assert events == [LEVEL_CHANGE]


@pytest.mark.unit
def test_the_same_values_are_just_written(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(
        UpdateSettingsRequest(cefr_level="C1", frequent_word_threshold="5.0"),
    )
    events.clear()
    use_case.update_settings(
        UpdateSettingsRequest(cefr_level="C1", frequent_word_threshold="5.0"),
    )
    assert events == [
        "write", "set cefr_level", f"set {FREQUENT_WORD_THRESHOLD_SETTING}", "committed",
    ]


@pytest.mark.unit
def test_the_default_value_written_explicitly_is_no_level_change(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(
        UpdateSettingsRequest(cefr_level="B2", frequent_word_threshold="off"),
    )
    assert events == [
        "write", "set cefr_level", f"set {FREQUENT_WORD_THRESHOLD_SETTING}", "committed",
    ]


@pytest.mark.unit
def test_an_unrelated_setting_is_no_level_change(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(
        UpdateSettingsRequest(anki_deck_name="Other", tts_speed=1.2, ai_model="opus"),
    )
    assert events == [
        "write", "set anki_deck_name", "set ai_model", "set tts_speed", "committed",
    ]


@pytest.mark.unit
def test_an_unrelated_setting_is_written_inside_one_write(
    use_case: ManageSettingsUseCase, events: list[str],
) -> None:
    use_case.update_settings(UpdateSettingsRequest(anki_deck_name="Other"))
    assert events == ["write", "set anki_deck_name", "committed"]
