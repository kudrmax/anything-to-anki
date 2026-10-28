"""`make update` against a local origin: the copy ends on the latest release and running,
or back where it was and running."""
from __future__ import annotations

import os
import plistlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "update.sh"
IDENTITY = ["-c", "user.name=Test", "-c", "user.email=test@example.com"]
OLD_DB = "schema 1.0.0"

# Every target records itself; `up` also records the database it found and "migrates" it,
# and fails on the version written in the FAIL_UP file. The snapshot fails while
# FAIL_SNAPSHOT exists.
FAKE_MAKEFILE = """\
VERSION := $(shell cat VERSION)

down setup-python app:
\t@echo $@ >> $(CALLS)

_db-snapshot:
\t@echo $@ >> $(CALLS)
\t@if [ -f $(FAIL_SNAPSHOT) ]; then echo "snapshot broke"; exit 1; fi
\t@cp data/app.db $(SNAPSHOT_DIR)/snapshot.db
\t@echo $(SNAPSHOT_DIR)/snapshot.db

_db-restore:
\t@echo "$@ $(SNAPSHOT)" >> $(CALLS)
\t@cp $(SNAPSHOT) data/app.db

up:
\t@echo "up $(VERSION) db=$$(cat data/app.db)" >> $(CALLS)
\t@echo "schema $(VERSION)" > data/app.db
\t@if [ -f $(FAIL_UP) ] && [ "$$(cat $(FAIL_UP))" = "$(VERSION)" ]; then echo broke; exit 1; fi
"""


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *IDENTITY, *args], cwd=cwd, check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


@dataclass(frozen=True)
class Copy:
    root: Path
    publisher: Path
    calls_file: Path
    fail_up: Path
    fail_snapshot: Path
    apps_dir: Path
    snapshot_dir: Path

    def release(self, version: str, *, macos_change: bool = False) -> None:
        (self.publisher / "VERSION").write_text(version)
        if macos_change:
            app_file = self.publisher / "frontends" / "macos" / "App.swift"
            app_file.parent.mkdir(parents=True, exist_ok=True)
            app_file.write_text(f"// {version}\n")
        git(self.publisher, "add", "-A")
        git(self.publisher, "commit", "-m", version)
        git(self.publisher, "tag", f"v{version}")
        git(self.publisher, "push", "--quiet", "origin", "HEAD", "--tags")

    def run(self) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "CALLS": str(self.calls_file),
            "FAIL_UP": str(self.fail_up),
            "FAIL_SNAPSHOT": str(self.fail_snapshot),
            "SNAPSHOT_DIR": str(self.snapshot_dir),
            "UPDATE_APPS_DIR": str(self.apps_dir),
            "MAKE": "make",
        }
        env.pop("MAKEFLAGS", None)
        env.pop("MAKELEVEL", None)
        return subprocess.run(
            ["/bin/bash", str(SCRIPT)], cwd=self.root, env=env, capture_output=True, text=True,
        )

    def calls(self) -> list[str]:
        if not self.calls_file.exists():
            return []
        return self.calls_file.read_text().splitlines()

    def head(self) -> str:
        return git(self.root, "rev-parse", "HEAD")

    def tag_commit(self, tag: str) -> str:
        return git(self.root, "rev-parse", f"{tag}^{{commit}}")

    def state(self) -> str:
        return (self.root / ".pids" / "update.state").read_text().strip()

    def db(self) -> str:
        return (self.root / "data" / "app.db").read_text().strip()

    def install_app(self, project_dir: Path) -> None:
        contents = self.apps_dir / "AnythingToAnki.app" / "Contents"
        contents.mkdir(parents=True)
        with (contents / "Info.plist").open("wb") as plist:
            plistlib.dump({"A2AProjectDir": str(project_dir)}, plist)


@pytest.fixture()
def copy(tmp_path: Path) -> Copy:
    bare = tmp_path / "origin.git"
    git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=master", str(bare))
    publisher = tmp_path / "publisher"
    git(tmp_path, "clone", "--quiet", str(bare), str(publisher))
    git(publisher, "checkout", "--quiet", "-b", "master")
    (publisher / "Makefile").write_text(FAKE_MAKEFILE)
    (publisher / ".gitignore").write_text("data/\n.pids/\n")
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    result = Copy(
        root=tmp_path / "installed",
        publisher=publisher,
        calls_file=tmp_path / "calls.txt",
        fail_up=tmp_path / "FAIL_UP",
        fail_snapshot=tmp_path / "FAIL_SNAPSHOT",
        apps_dir=tmp_path / "Applications",
        snapshot_dir=snapshot_dir,
    )
    result.release("1.0.0")
    git(tmp_path, "clone", "--quiet", str(bare), str(result.root))
    (result.root / "data").mkdir()
    (result.root / "data" / "app.db").write_text(OLD_DB)
    return result


def test_head_ahead_of_the_latest_tag_is_left_as_it_is(copy: Copy) -> None:
    (copy.publisher / "unreleased.txt").write_text("work in progress")
    git(copy.publisher, "add", "-A")
    git(copy.publisher, "commit", "-m", "unreleased")
    git(copy.publisher, "push", "--quiet", "origin", "HEAD")
    git(copy.root, "pull", "--quiet", "--ff-only")
    head = copy.head()

    result = copy.run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Already up to date" in result.stdout
    assert copy.head() == head
    assert copy.calls() == []
    assert copy.state() == "done"


def test_moves_to_the_highest_release_tag_and_starts(copy: Copy) -> None:
    git(copy.root, "checkout", "--quiet", "v1.0.0")
    copy.release("1.2.0")
    copy.release("1.10.0")
    git(copy.publisher, "tag", "v2.0.0-rc1")
    git(copy.publisher, "push", "--quiet", "origin", "--tags")

    result = copy.run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert copy.head() == copy.tag_commit("v1.10.0")
    assert copy.calls() == [
        "down", "_db-snapshot", "setup-python", f"up 1.10.0 db={OLD_DB}",
    ]
    assert copy.state() == "done"


def test_failed_start_of_the_new_version_rolls_back_to_the_old_one(copy: Copy) -> None:
    old_head = copy.head()
    copy.release("1.1.0")
    copy.fail_up.write_text("1.1.0")

    result = copy.run()

    assert result.returncode == 1
    assert copy.head() == old_head
    assert git(copy.root, "symbolic-ref", "--short", "HEAD") == "master"
    snapshot = copy.snapshot_dir / "snapshot.db"
    assert copy.calls() == [
        "down",
        "_db-snapshot",
        "setup-python",
        f"up 1.1.0 db={OLD_DB}",
        f"_db-restore {snapshot}",
        "setup-python",
        f"up 1.0.0 db={OLD_DB}",
    ]
    assert copy.db() == OLD_DB
    assert copy.state() == "failed"


def test_failure_before_checkout_starts_the_old_version_again(copy: Copy) -> None:
    old_head = copy.head()
    copy.release("1.1.0")
    copy.fail_snapshot.write_text("")

    result = copy.run()

    assert result.returncode == 1
    assert copy.head() == old_head
    assert copy.calls() == ["down", "_db-snapshot", f"up 1.0.0 db={OLD_DB}"]
    assert copy.state() == "failed"


def test_uncommitted_changes_refuse_the_update(copy: Copy) -> None:
    copy.release("1.1.0")
    (copy.root / "VERSION").write_text("edited")

    result = copy.run()

    assert result.returncode == 1
    assert "VERSION" in result.stdout + result.stderr
    assert "commit or stash" in (result.stdout + result.stderr).lower()
    assert copy.calls() == []
    assert copy.state() == "failed"


def test_unreachable_origin_fails_without_touching_the_copy(copy: Copy) -> None:
    head = copy.head()
    git(copy.root, "remote", "remove", "origin")

    result = copy.run()

    assert result.returncode == 1
    assert "Could not reach origin" in result.stdout + result.stderr
    assert copy.head() == head
    assert copy.calls() == []
    assert copy.state() == "failed"


def test_app_of_this_copy_is_rebuilt_when_its_code_changed(copy: Copy) -> None:
    copy.install_app(copy.root)
    copy.release("1.1.0", macos_change=True)

    result = copy.run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert copy.calls() == ["down", "_db-snapshot", "setup-python", "app", f"up 1.1.0 db={OLD_DB}"]


def test_app_is_not_rebuilt_when_its_code_did_not_change(copy: Copy) -> None:
    copy.install_app(copy.root)
    copy.release("1.1.0")

    result = copy.run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "app" not in copy.calls()


def test_app_of_another_copy_is_not_rebuilt(copy: Copy, tmp_path: Path) -> None:
    other = tmp_path / "other-copy"
    other.mkdir()
    copy.install_app(other)
    copy.release("1.1.0", macos_change=True)

    result = copy.run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "app" not in copy.calls()


def test_rebuilt_app_is_rebuilt_back_on_rollback(copy: Copy) -> None:
    copy.install_app(copy.root)
    copy.release("1.1.0", macos_change=True)
    copy.fail_up.write_text("1.1.0")

    result = copy.run()

    assert result.returncode == 1
    assert copy.calls()[-3:] == ["setup-python", "app", f"up 1.0.0 db={OLD_DB}"]
