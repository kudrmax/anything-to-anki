"""Fakes of the release ports: the installed copy and the published releases."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from backend.domain.exceptions import LongOperationInProgressError
from backend.domain.ports.installed_release import InstalledRelease
from backend.domain.ports.release_source import ReleaseSource
from backend.domain.ports.unit_of_work import UnitOfWork
from backend.domain.value_objects.app_version import AppVersion

if TYPE_CHECKING:
    from collections.abc import Iterator


def changelog(*versions: str) -> str:
    entries = "\n\n".join(
        f"## {version} — 2026-10-01\n\nSummary {version}.\n\n### New\n\n- thing {version}"
        for version in reversed(versions)
    )
    return f"# Changelog\n\n{entries}\n"


class FakeInstalledRelease(InstalledRelease):
    def __init__(self, version: str, text: str, assets: dict[str, bytes] | None = None) -> None:
        self._version = AppVersion.parse(version)
        self._text = text
        self._assets = assets or {}

    def version(self) -> AppVersion:
        return self._version

    def changelog_text(self) -> str:
        return self._text

    def asset(self, path: str) -> bytes | None:
        return self._assets.get(path)


class FakeReleaseSource(ReleaseSource):
    def __init__(
        self, latest: str | None, text: str | None = None, assets: dict[str, bytes] | None = None,
    ) -> None:
        self._latest = AppVersion.parse(latest) if latest else None
        self._text = text
        self._assets = assets or {}
        self.latest_calls = 0

    def latest(self) -> AppVersion | None:
        self.latest_calls += 1
        return self._latest

    def changelog_text(self, version: AppVersion) -> str | None:
        return self._text

    def asset(self, version: AppVersion, path: str) -> bytes | None:
        return self._assets.get(f"{version}/{path}")


class PlainUnitOfWork(UnitOfWork):
    """Transactions that do nothing: the fake settings are written at once."""

    @contextmanager
    def write(self) -> Iterator[None]:
        yield

    @contextmanager
    def read(self) -> Iterator[None]:
        yield


class LockedUnitOfWork(UnitOfWork):
    """A long operation runs: the write gate refuses every write."""

    @contextmanager
    def write(self) -> Iterator[None]:
        raise LongOperationInProgressError
        yield

    @contextmanager
    def read(self) -> Iterator[None]:
        yield
