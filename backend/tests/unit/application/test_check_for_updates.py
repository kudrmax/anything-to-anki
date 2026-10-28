from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from backend.application.use_cases.check_for_updates import (
    UPDATE_CHECK_INTERVAL,
    UPDATE_CHECKED_AT_KEY,
    UPDATE_LATEST_VERSION_KEY,
    CheckForUpdatesUseCase,
)
from backend.domain.services.changelog_parser import ChangelogParser

from tests.decision_support import NOW, FixedClock
from tests.release_support import (
    FakeInstalledRelease,
    FakeReleaseSource,
    LockedUnitOfWork,
    PlainUnitOfWork,
    changelog,
)
from tests.source_order_support import InMemorySettingsRepository

if TYPE_CHECKING:
    from backend.domain.ports.unit_of_work import UnitOfWork

REMOTE_CHANGELOG = changelog("1.0.0", "1.1.0", "1.2.0")


def _use_case(
    source: FakeReleaseSource,
    settings: InMemorySettingsRepository,
    clock: FixedClock | None = None,
    unit_of_work: UnitOfWork | None = None,
) -> CheckForUpdatesUseCase:
    installed = FakeInstalledRelease("1.0.0", changelog("1.0.0"))
    return CheckForUpdatesUseCase(
        installed, source, settings, clock or FixedClock(), ChangelogParser(),
        unit_of_work or PlainUnitOfWork(),
    )


@pytest.mark.unit
def test_newer_release_is_available_with_the_entries_after_the_installed_one() -> None:
    source = FakeReleaseSource("1.2.0", REMOTE_CHANGELOG)

    status = _use_case(source, InMemorySettingsRepository()).execute(force=False)

    assert (status.current, status.latest, status.available) == ("1.0.0", "1.2.0", True)
    assert [entry.version for entry in status.entries] == ["1.2.0", "1.1.0"]
    assert not status.check_failed


@pytest.mark.unit
def test_latest_equal_to_installed_is_not_available() -> None:
    source = FakeReleaseSource("1.0.0", changelog("1.0.0"))

    status = _use_case(source, InMemorySettingsRepository()).execute(force=False)

    assert (status.available, status.entries) == (False, [])


@pytest.mark.unit
def test_fresh_cache_is_used_without_asking_the_source() -> None:
    settings = InMemorySettingsRepository()
    settings.set(UPDATE_CHECKED_AT_KEY, (NOW - timedelta(hours=1)).isoformat())
    settings.set(UPDATE_LATEST_VERSION_KEY, "1.2.0")
    source = FakeReleaseSource("1.5.0", REMOTE_CHANGELOG)

    status = _use_case(source, settings).execute(force=False)

    assert source.latest_calls == 0
    assert status.latest == "1.2.0"


@pytest.mark.unit
def test_cache_older_than_a_day_asks_the_source_and_is_rewritten() -> None:
    settings = InMemorySettingsRepository()
    settings.set(UPDATE_CHECKED_AT_KEY, (NOW - UPDATE_CHECK_INTERVAL).isoformat())
    settings.set(UPDATE_LATEST_VERSION_KEY, "1.1.0")
    source = FakeReleaseSource("1.2.0", REMOTE_CHANGELOG)

    status = _use_case(source, settings).execute(force=False)

    assert source.latest_calls == 1
    assert status.latest == "1.2.0"
    assert settings.get(UPDATE_LATEST_VERSION_KEY) == "1.2.0"
    assert settings.get(UPDATE_CHECKED_AT_KEY) == NOW.isoformat()


@pytest.mark.unit
def test_force_asks_the_source_despite_a_fresh_cache() -> None:
    settings = InMemorySettingsRepository()
    settings.set(UPDATE_CHECKED_AT_KEY, NOW.isoformat())
    settings.set(UPDATE_LATEST_VERSION_KEY, "1.1.0")
    source = FakeReleaseSource("1.2.0", REMOTE_CHANGELOG)

    status = _use_case(source, settings).execute(force=True)

    assert source.latest_calls == 1
    assert status.latest == "1.2.0"


@pytest.mark.unit
def test_forced_check_that_learns_nothing_reports_the_failure() -> None:
    source = FakeReleaseSource(None)

    status = _use_case(source, InMemorySettingsRepository()).execute(force=True)

    assert (status.check_failed, status.available, status.latest) == (True, False, None)


@pytest.mark.unit
def test_unforced_check_that_learns_nothing_is_not_a_failure() -> None:
    source = FakeReleaseSource(None)

    status = _use_case(source, InMemorySettingsRepository()).execute(force=False)

    assert (status.check_failed, status.available) == (False, False)


@pytest.mark.unit
def test_forced_check_fails_when_the_fetch_fails_even_with_a_cached_version() -> None:
    settings = InMemorySettingsRepository()
    settings.set(UPDATE_CHECKED_AT_KEY, (NOW - timedelta(days=3)).isoformat())
    settings.set(UPDATE_LATEST_VERSION_KEY, "1.0.0")

    status = _use_case(FakeReleaseSource(None), settings).execute(force=True)

    assert (status.check_failed, status.available, status.latest) == (True, False, "1.0.0")


@pytest.mark.unit
def test_check_during_a_long_operation_answers_without_persisting() -> None:
    settings = InMemorySettingsRepository()
    source = FakeReleaseSource("1.2.0", REMOTE_CHANGELOG)

    status = _use_case(source, settings, unit_of_work=LockedUnitOfWork()).execute(force=False)

    assert (status.latest, status.available) == ("1.2.0", True)
    assert settings.values == {}
