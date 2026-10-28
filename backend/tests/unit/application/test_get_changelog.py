from __future__ import annotations

import pytest
from backend.application.use_cases.get_changelog import (
    CHANGELOG_SEEN_VERSION_KEY,
    GetChangelogUseCase,
)
from backend.domain.services.changelog_parser import ChangelogParser

from tests.release_support import (
    FakeInstalledRelease,
    LockedUnitOfWork,
    PlainUnitOfWork,
    changelog,
)
from tests.source_order_support import InMemorySettingsRepository


def _use_case(current: str, settings: InMemorySettingsRepository) -> GetChangelogUseCase:
    text = changelog("1.0.0", "1.1.0", "1.2.0", "1.3.0")
    installed = FakeInstalledRelease(current, text)
    return GetChangelogUseCase(installed, settings, ChangelogParser(), PlainUnitOfWork())


@pytest.mark.unit
def test_all_lists_every_entry_newest_first() -> None:
    entries = _use_case("1.2.0", InMemorySettingsRepository()).all()

    assert [entry.version for entry in entries] == ["1.3.0", "1.2.0", "1.1.0", "1.0.0"]


@pytest.mark.unit
def test_fresh_install_has_nothing_unseen_and_remembers_the_version() -> None:
    settings = InMemorySettingsRepository()

    assert _use_case("1.2.0", settings).unseen() == []
    assert settings.get(CHANGELOG_SEEN_VERSION_KEY) == "1.2.0"


@pytest.mark.unit
def test_every_skipped_release_up_to_the_installed_one_is_unseen() -> None:
    settings = InMemorySettingsRepository()
    settings.set(CHANGELOG_SEEN_VERSION_KEY, "1.0.0")

    unseen = _use_case("1.2.0", settings).unseen()

    assert [entry.version for entry in unseen] == ["1.2.0", "1.1.0"]


@pytest.mark.unit
def test_mark_seen_writes_the_installed_version() -> None:
    settings = InMemorySettingsRepository()
    settings.set(CHANGELOG_SEEN_VERSION_KEY, "1.0.0")
    use_case = _use_case("1.2.0", settings)

    use_case.mark_seen()

    assert settings.get(CHANGELOG_SEEN_VERSION_KEY) == "1.2.0"
    assert use_case.unseen() == []


@pytest.mark.unit
def test_fresh_install_during_a_long_operation_has_nothing_unseen_and_persists_nothing() -> None:
    settings = InMemorySettingsRepository()
    installed = FakeInstalledRelease("1.2.0", changelog("1.0.0", "1.1.0", "1.2.0"))
    use_case = GetChangelogUseCase(installed, settings, ChangelogParser(), LockedUnitOfWork())

    assert use_case.unseen() == []
    assert settings.values == {}
