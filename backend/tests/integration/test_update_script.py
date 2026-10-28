"""`make update` against a local origin: the copy ends on the latest release and running,
or back where it was and running."""
from __future__ import annotations

import fcntl
import os
import plistlib
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.app_version import AppVersion
from backend.infrastructure.adapters.release.git_release_source import GitReleaseSource

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.integration

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "update.sh"
IDENTITY = ["-c", "user.name=Test", "-c", "user.email=test@example.com"]
OLD_DB = "schema 1.0.0"
# Generous for a run of the fake Makefile; a hang fails the test instead of the suite.
WAIT_S = 20

# Every target records itself. `up` records the database it found, "migrates" it and
# leaves the copy's processes running, even when it then fails; `down` stops them. A
# restore refuses to run over running processes. `setup-python` and the frontend install
# in `up` (run when package-lock.json is newer than the installed packages, as in the real
# Makefile) write the version into a marker of the packages they install. Files in FLAGS
# switch failures on: fail_up (fails on the version written in it), fail_snapshot,
# fail_restore, fail_setup, fail_npm (both fail as without a network, after breaking the
# packages); hold makes `down` wait while it says "hold"; spawn makes `up` leave a real
# background process; linger makes `down` leave one that keeps its output open.
FAKE_MAKEFILE = """\
VERSION := $(shell cat VERSION)
# Outlives any test: a step that leaves this behind must not keep the update waiting.
LINGER_S := 600
STAMP := frontends/web/node_modules/.package-lock.json
NPM_LOCK := frontends/web/package-lock.json

down:
\t@echo $@ >> $(CALLS)
\t@while [ "$$(cat $(FLAGS)/hold 2>/dev/null)" = hold ]; do sleep 0.05; done
\t@if [ -f $(FLAGS)/linger ]; then sleep $(LINGER_S) & fi
\t@echo stopped > $(FLAGS)/processes

setup-python:
\t@echo $@ >> $(CALLS)
\t@if [ -f $(FLAGS)/fail_setup ]; then \\
\t    echo broken > .venv/marker; echo "pip: no network"; exit 1; \\
\tfi
\t@echo $(VERSION) > .venv/marker

app:
\t@echo $@ >> $(CALLS)

_db-snapshot:
\t@echo $@ >> $(CALLS)
\t@if [ -f $(FLAGS)/fail_snapshot ]; then echo "snapshot broke"; exit 1; fi
\t@if [ -f data/app.db ]; then \\
\t    cp data/app.db $(FLAGS)/snapshot.db && echo $(FLAGS)/snapshot.db; \\
\telse echo NO_DATABASE; fi

_db-restore:
\t@echo "$@ $(VERSION) $(SNAPSHOT)" >> $(CALLS)
\t@if [ "$$(cat $(FLAGS)/processes)" = running ]; then echo "restore while running"; exit 1; fi
\t@if [ -f $(FLAGS)/fail_restore ]; then echo "restore broke"; exit 1; fi
\t@if [ "$(SNAPSHOT)" = --none ]; then mv data/app.db $(FLAGS)/aside.db; \\
\telse cp $(SNAPSHOT) data/app.db; fi

up:
\t@echo "up $(VERSION) db=$$(cat data/app.db 2>/dev/null)" >> $(CALLS)
\t@if ! [ $(STAMP) -nt $(NPM_LOCK) ]; then \\
\t    if [ -f $(FLAGS)/fail_npm ]; then \\
\t        echo broken > frontends/web/node_modules/marker; echo "npm ci: no network"; exit 1; \\
\t    fi; \\
\t    echo $(VERSION) > frontends/web/node_modules/marker; touch $(STAMP); \\
\tfi
\t@echo running > $(FLAGS)/processes
\t@mkdir -p data && echo "schema $(VERSION)" > data/app.db
\t@if [ -f $(FLAGS)/spawn ]; then sleep 5 </dev/null >/dev/null 2>&1 & fi
\t@if [ "$$(cat $(FLAGS)/fail_up 2>/dev/null)" = "$(VERSION)" ]; then echo broke; exit 1; fi
"""


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *IDENTITY, *args], cwd=cwd, check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


GITIGNORE = "data/\n.pids/\n.logs/\n.venv/\nfrontends/web/node_modules/\n"
FAKE_TRASH = """\
#!/bin/bash
for path in "$@"; do mv "$path" "$TRASH_DIR/$(basename "$path").$$.$RANDOM"; done
"""
# Long enough in the past that the installed packages are newer than the lock, as after a
# real install.
INSTALLED_LONG_AGO_S = 3600


@dataclass(frozen=True)
class Copy:
    root: Path
    publisher: Path
    calls_file: Path
    flags: Path
    apps_dir: Path
    trash_dir: Path
    fake_trash: Path

    def release(
        self,
        version: str,
        *,
        macos_change: bool = False,
        npm_change: bool = False,
    ) -> None:
        (self.publisher / "VERSION").write_text(version)
        if macos_change:
            app_file = self.publisher / "frontends" / "macos" / "App.swift"
            app_file.parent.mkdir(parents=True, exist_ok=True)
            app_file.write_text(f"// {version}\n")
        if npm_change:
            npm_lock = self.publisher / "frontends" / "web" / "package-lock.json"
            npm_lock.write_text(f'{{"v": "{version}"}}\n')
        git(self.publisher, "add", "-A")
        git(self.publisher, "commit", "-m", version)
        git(self.publisher, "tag", f"v{version}")
        git(self.publisher, "push", "--quiet", "origin", "HEAD", "--tags")

    def flag(self, name: str, value: str = "") -> None:
        (self.flags / name).write_text(value)

    def env(self) -> dict[str, str]:
        env = {
            **os.environ,
            "CALLS": str(self.calls_file),
            "FLAGS": str(self.flags),
            "UPDATE_APPS_DIR": str(self.apps_dir),
            "UPDATE_TRASH": str(self.fake_trash),
            "TRASH_DIR": str(self.trash_dir),
            "MAKE": "make",
        }
        env.pop("MAKEFLAGS", None)
        env.pop("MAKELEVEL", None)
        return env

    def start(self) -> subprocess.Popen[str]:
        return subprocess.Popen(
            ["/bin/bash", str(SCRIPT)], cwd=self.root, env=self.env(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )

    def run(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["/bin/bash", str(SCRIPT)], cwd=self.root, env=self.env(),
            capture_output=True, text=True,
        )

    @property
    def snapshot(self) -> Path:
        return self.flags / "snapshot.db"

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

    def error(self) -> str:
        return (self.root / ".pids" / "update.error").read_text()

    def log(self) -> str:
        return (self.root / ".logs" / "update.log").read_text()

    def venv_marker(self) -> str:
        return (self.root / ".venv" / "marker").read_text().strip()

    def node_modules_marker(self) -> str:
        return (self.root / "frontends" / "web" / "node_modules" / "marker").read_text().strip()

    @property
    def backup_dir(self) -> Path:
        return self.root / ".pids" / "update-backup"

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
    (publisher / ".gitignore").write_text(GITIGNORE)
    (publisher / "frontends" / "web").mkdir(parents=True)
    (publisher / "frontends" / "web" / "package-lock.json").write_text('{"v": "1.0.0"}\n')
    flags = tmp_path / "flags"
    flags.mkdir()
    trash_dir = tmp_path / "Trash"
    trash_dir.mkdir()
    fake_trash = tmp_path / "fake-trash.sh"
    fake_trash.write_text(FAKE_TRASH)
    fake_trash.chmod(0o755)
    result = Copy(
        root=tmp_path / "installed",
        publisher=publisher,
        calls_file=tmp_path / "calls.txt",
        flags=flags,
        apps_dir=tmp_path / "Applications",
        trash_dir=trash_dir,
        fake_trash=fake_trash,
    )
    result.flag("processes", "running")
    result.release("1.0.0")
    git(tmp_path, "clone", "--quiet", str(bare), str(result.root))
    (result.root / "data").mkdir()
    (result.root / "data" / "app.db").write_text(OLD_DB)
    _install_packages(result.root)
    return result


def _install_packages(root: Path) -> None:
    (root / ".venv").mkdir()
    (root / ".venv" / "marker").write_text("1.0.0\n")
    node_modules = root / "frontends" / "web" / "node_modules"
    node_modules.mkdir()
    (node_modules / "marker").write_text("1.0.0\n")
    (node_modules / ".package-lock.json").write_text("{}\n")
    lock = root / "frontends" / "web" / "package-lock.json"
    long_ago = time.time() - INSTALLED_LONG_AGO_S
    os.utime(lock, (long_ago, long_ago))


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
    assert not copy.backup_dir.exists()


def test_failed_start_of_the_new_version_rolls_back_to_the_old_one(copy: Copy) -> None:
    old_head = copy.head()
    copy.release("1.1.0")
    copy.flag("fail_up", "1.1.0")

    result = copy.run()

    assert result.returncode == 1
    assert copy.head() == old_head
    assert git(copy.root, "symbolic-ref", "--short", "HEAD") == "master"
    # The failed start left processes running: they stop before the restore, and the
    # restore runs on the old code, the code that took the copy.
    assert copy.calls() == [
        "down",
        "_db-snapshot",
        "setup-python",
        f"up 1.1.0 db={OLD_DB}",
        "down",
        f"_db-restore 1.0.0 {copy.snapshot}",
        f"up 1.0.0 db={OLD_DB}",
    ]
    assert copy.db() == OLD_DB
    assert copy.state() == "failed"


def test_failure_before_checkout_starts_the_old_version_again(copy: Copy) -> None:
    old_head = copy.head()
    copy.release("1.1.0")
    copy.flag("fail_snapshot")

    result = copy.run()

    assert result.returncode == 1
    assert copy.head() == old_head
    assert copy.calls() == ["down", "_db-snapshot", "down", f"up 1.0.0 db={OLD_DB}"]
    assert copy.state() == "failed"


def test_failed_python_install_rolls_back_without_the_network(copy: Copy) -> None:
    old_head = copy.head()
    copy.release("1.1.0")
    copy.flag("fail_setup")

    result = copy.run()

    assert result.returncode == 1
    assert copy.head() == old_head
    assert copy.calls() == [
        "down", "_db-snapshot", "setup-python", "down",
        f"_db-restore 1.0.0 {copy.snapshot}", f"up 1.0.0 db={OLD_DB}",
    ]
    assert copy.venv_marker() == "1.0.0"
    assert (copy.flags / "processes").read_text().strip() == "running"
    assert copy.state() == "failed"
    assert not copy.backup_dir.exists()


def test_failed_frontend_install_rolls_back_without_the_network(copy: Copy) -> None:
    old_head = copy.head()
    copy.release("1.1.0", npm_change=True)
    copy.flag("fail_npm")

    result = copy.run()

    assert result.returncode == 1, result.stdout + result.stderr
    assert copy.head() == old_head
    assert copy.calls()[-1] == f"up 1.0.0 db={OLD_DB}"
    assert copy.node_modules_marker() == "1.0.0"
    assert (copy.flags / "processes").read_text().strip() == "running"
    assert copy.state() == "failed"


def test_failure_says_which_step_broke_and_how(copy: Copy) -> None:
    copy.release("1.1.0")
    copy.flag("fail_up", "1.1.0")

    copy.run()

    error = copy.error()
    assert error.startswith("Failed step: make up\n")
    assert "broke" in error


def test_rollback_names_the_release_it_returns_to(copy: Copy) -> None:
    copy.release("1.1.0")
    copy.flag("fail_up", "1.1.0")

    result = copy.run()

    assert "Rolling back to v1.0.0" in result.stdout
    assert "Rolled back to v1.0.0" in result.stdout


def test_every_run_is_logged_under_its_own_header(copy: Copy) -> None:
    copy.release("1.1.0")

    result = copy.run()

    log = copy.log()
    assert log.startswith("=== make update ")
    assert "Updated to v1.1.0." in result.stdout
    assert "Updated to v1.1.0." in log


def test_worktree_refuses_the_update(copy: Copy, tmp_path: Path) -> None:
    copy.release("1.1.0")
    linked = tmp_path / "linked"
    git(copy.root, "worktree", "add", "--quiet", str(linked), "HEAD")

    result = subprocess.run(
        ["/bin/bash", str(SCRIPT)], cwd=linked, env=copy.env(), capture_output=True, text=True,
    )

    assert result.returncode == 1
    assert "main checkout" in result.stdout
    assert (linked / ".pids" / "update.state").read_text() == "failed"
    assert "main checkout" in (linked / ".pids" / "update.error").read_text()
    assert copy.calls() == []


def test_failed_rollback_without_a_database_says_there_was_none(copy: Copy) -> None:
    (copy.root / "data" / "app.db").rename(copy.flags / "nothing-here")
    copy.release("1.1.0")
    copy.flag("fail_up", "1.1.0")
    copy.flag("fail_restore")

    result = copy.run()

    assert "There was no database before the update." in result.stdout
    assert "SNAPSHOT=--none" in result.stdout
    assert copy.backup_dir.exists()


def test_lock_handed_over_by_the_app_is_kept(copy: Copy) -> None:
    copy.release("1.1.0")
    (copy.root / ".pids").mkdir()
    lock_path = copy.root / ".pids" / "update.script.lock"
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = subprocess.run(
            ["/bin/sh", "-c", f'exec "$@" 9>&{lock.fileno()}', "update", "/bin/bash", str(SCRIPT)],
            cwd=copy.root, env=copy.env(), capture_output=True, text=True,
            pass_fds=(lock.fileno(),),
        )

    assert result.returncode == 0, result.stdout + result.stderr
    assert copy.state() == "done"


def test_a_tag_moved_on_origin_does_not_stop_the_update(copy: Copy) -> None:
    copy.release("1.1.0")
    assert copy.run().returncode == 0
    (copy.publisher / "notes.txt").write_text("moved")
    git(copy.publisher, "add", "-A")
    git(copy.publisher, "commit", "-m", "moved")
    git(copy.publisher, "tag", "--force", "v1.1.0")
    git(copy.publisher, "push", "--quiet", "--force", "origin", "HEAD", "--tags")
    copy.release("1.2.0")

    result = copy.run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert copy.head() == copy.tag_commit("v1.2.0")


def test_a_step_that_leaves_a_process_holding_its_output_does_not_stall(copy: Copy) -> None:
    copy.release("1.1.0")
    copy.flag("linger")

    result = subprocess.run(
        ["/bin/bash", str(SCRIPT)], cwd=copy.root, env=copy.env(),
        capture_output=True, text=True, timeout=WAIT_S,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert copy.state() == "done"


def test_the_log_is_complete_once_the_lock_is_free(copy: Copy) -> None:
    copy.release("1.1.0")
    copy.flag("fail_up", "1.1.0")
    process = subprocess.Popen(
        ["/bin/bash", str(SCRIPT)], cwd=copy.root, env=copy.env(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(lambda: (copy.root / ".pids" / "update.script.lock").exists())
        _wait_for(lambda: not _lock_held(copy.root / ".pids" / "update.script.lock"))

        assert copy.state() == "failed"
        assert copy.log().rstrip().endswith("Rolled back to v1.0.0 and started.")
    finally:
        process.wait(timeout=WAIT_S)


def test_a_copy_stopped_by_a_failed_rollback_is_recovered_first(copy: Copy) -> None:
    copy.release("1.1.0")
    copy.flag("fail_up", "1.1.0")
    copy.flag("fail_restore")
    copy.run()
    kept = sorted(path.name for path in copy.backup_dir.iterdir())
    calls = copy.calls()

    again = copy.run()

    assert again.returncode == 1
    assert "Finish its recovery first" in again.stdout
    assert "make _db-restore" in again.stdout
    assert sorted(path.name for path in copy.backup_dir.iterdir()) == kept
    assert copy.calls() == calls


def test_missing_packages_refuse_the_update(copy: Copy) -> None:
    copy.release("1.1.0")
    (copy.root / "frontends" / "web" / "node_modules").rename(copy.flags / "node_modules")

    result = copy.run()

    assert result.returncode == 1
    assert "make setup" in result.stdout
    assert copy.calls() == []


def test_the_apps_check_of_the_lock_never_makes_a_terminal_run_refuse(copy: Copy) -> None:
    """The app checks the lock by taking it shared for a moment, under the start lock. A
    terminal run that tries its lock at that moment waits for the check instead of
    refusing."""
    copy.release("1.1.0")
    pids = copy.root / ".pids"
    pids.mkdir()
    start_lock = pids / "update.lock"
    with start_lock.open("a") as start, (pids / "update.script.lock").open("a") as probe:
        fcntl.flock(start, fcntl.LOCK_EX)
        fcntl.flock(probe, fcntl.LOCK_SH)
        process = copy.start()
        _wait_for(lambda: _openers(start_lock) > 1)
        fcntl.flock(probe, fcntl.LOCK_UN)
    stdout, _ = process.communicate(timeout=WAIT_S)

    assert process.returncode == 0, stdout
    assert copy.state() == "done"


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
    assert copy.calls() == [
        "down", "_db-snapshot", "setup-python", "app", f"up 1.1.0 db={OLD_DB}",
    ]


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
    copy.flag("fail_up", "1.1.0")

    result = copy.run()

    assert result.returncode == 1
    assert copy.calls()[-4:] == [
        "down", f"_db-restore 1.0.0 {copy.snapshot}", "app", f"up 1.0.0 db={OLD_DB}",
    ]


def test_failed_restore_leaves_the_copy_stopped_and_says_where_the_copy_is(copy: Copy) -> None:
    copy.release("1.1.0")
    copy.flag("fail_up", "1.1.0")
    copy.flag("fail_restore")

    result = copy.run()

    assert result.returncode == 1
    assert copy.calls()[-1] == f"_db-restore 1.0.0 {copy.snapshot}"
    assert str(copy.snapshot) in result.stdout
    assert "stopped" in result.stdout
    assert copy.state() == "failed"


def test_copy_without_a_database_sets_the_new_one_aside_on_rollback(copy: Copy) -> None:
    (copy.root / "data" / "app.db").rename(copy.flags / "nothing-here")
    copy.release("1.1.0")
    copy.flag("fail_up", "1.1.0")

    result = copy.run()

    assert result.returncode == 1
    assert copy.calls()[-2:] == ["_db-restore 1.0.0 --none", "up 1.0.0 db="]
    assert (copy.flags / "aside.db").read_text().strip() == "schema 1.1.0"


def test_garbage_snapshot_path_does_not_switch_versions(copy: Copy) -> None:
    makefile = copy.root / "Makefile"
    makefile.write_text(makefile.read_text().replace(
        "cp data/app.db $(FLAGS)/snapshot.db && echo $(FLAGS)/snapshot.db",
        "echo /nowhere/snapshot.db",
    ))
    git(copy.root, "commit", "--quiet", "-am", "snapshot prints garbage")
    copy.release("1.1.0")
    old_head = copy.head()

    result = copy.run()

    assert result.returncode == 1
    assert copy.head() == old_head
    assert copy.calls() == ["down", "_db-snapshot", "down", f"up 1.0.0 db={OLD_DB}"]


def test_second_update_at_the_same_time_refuses_and_leaves_the_first_alone(
    copy: Copy,
) -> None:
    copy.release("1.1.0")
    copy.flag("hold", "hold")
    first = copy.start()
    try:
        _wait_for(lambda: "down" in copy.calls())
        state_of_first = copy.state()

        second = copy.run()

        assert second.returncode == 1
        assert "already running" in second.stderr
        assert copy.state() == state_of_first == "running"
    finally:
        copy.flag("hold", "go")
        first.wait(timeout=30)
    assert first.returncode == 0
    assert copy.state() == "done"


def test_lock_of_a_dead_run_does_not_block(copy: Copy) -> None:
    (copy.root / ".pids").mkdir()
    (copy.root / ".pids" / "update.script.lock").write_text("999999")
    copy.release("1.1.0")

    result = copy.run()

    assert result.returncode == 0, result.stdout + result.stderr


def test_servers_left_running_do_not_hold_the_lock(copy: Copy) -> None:
    copy.release("1.1.0")
    copy.flag("spawn")
    assert copy.run().returncode == 0

    again = copy.run()

    assert again.returncode == 0, again.stdout + again.stderr
    assert "Already up to date" in again.stdout


def test_script_and_release_source_pick_the_same_latest_tag(copy: Copy) -> None:
    copy.release("1.2.0")
    copy.release("1.10.0")
    git(copy.publisher, "tag", "v2.0.0-rc1")
    git(copy.publisher, "tag", "not-a-release")
    git(copy.publisher, "push", "--quiet", "origin", "--tags")
    git(copy.root, "checkout", "--quiet", "v1.0.0")

    result = copy.run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert copy.head() == copy.tag_commit("v1.10.0")
    assert GitReleaseSource(copy.root).latest() == AppVersion(1, 10, 0)


def _lock_held(path: Path) -> bool:
    with path.open() as probe:
        try:
            fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(probe, fcntl.LOCK_UN)
        return False


def _openers(path: Path) -> int:
    """How many processes have the file open."""
    found = subprocess.run(["lsof", "-t", str(path)], capture_output=True, text=True)
    return len(found.stdout.split())


def _wait_for(condition: Callable[[], bool], timeout: float = WAIT_S) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.05)
