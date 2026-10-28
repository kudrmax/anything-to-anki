from __future__ import annotations

import fcntl
import sys
import threading
import time
from typing import TYPE_CHECKING

import pytest
from backend.domain.exceptions import UpdateAlreadyRunningError
from backend.domain.value_objects.update_progress import (
    UpdateState,
    UpdateStep,
    UpdateStepStatus,
)
from backend.infrastructure.adapters.release.script_update_runner import (
    ERROR_FILE,
    LOG_FILE,
    LOG_TAIL_LINES,
    PROGRESS_FILE,
    SCRIPT_LOCK_FD,
    SCRIPT_LOCK_FILE,
    START_LOCK_FILE,
    STATE_FILE,
    ScriptUpdateRunner,
)

if TYPE_CHECKING:
    from pathlib import Path

WAIT_S = 10
# Long enough for an unblocked check to finish many times over.
CHECK_BLOCKED_S = 0.5


def _wait_for(path: Path, text: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if path.exists() and text in path.read_text():
            return
        time.sleep(0.05)
    pytest.fail(f"{path} never got {text!r}")


@pytest.mark.unit
def test_without_a_state_file_it_is_idle(tmp_path: Path) -> None:
    assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.IDLE


@pytest.mark.unit
def test_start_writes_running_and_runs_the_command_in_the_project_dir(tmp_path: Path) -> None:
    marker = tmp_path / "cwd"
    code = f"import os, time; open({str(marker)!r}, 'w').write(os.getcwd()); time.sleep(2)"
    runner = ScriptUpdateRunner(tmp_path, [sys.executable, "-c", code])

    runner.start()

    assert runner.state().state is UpdateState.RUNNING
    _wait_for(marker, tmp_path.name)


@pytest.mark.unit
def test_the_command_writes_nothing_to_the_log_itself(tmp_path: Path) -> None:
    """The script logs on its own; the runner must not log its output a second time."""
    command = [sys.executable, "-c", "print('twice', flush=True)"]
    runner = ScriptUpdateRunner(tmp_path, command)

    runner.start()

    _wait_for_state(runner, UpdateState.FAILED)
    log = tmp_path / LOG_FILE
    assert not log.exists() or "twice" not in log.read_text()


@pytest.mark.unit
def test_the_script_gets_the_lock_already_taken(tmp_path: Path) -> None:
    """No moment between the click and the script's start reads as a dead update."""
    marker = tmp_path / "lock-at-start"
    code = (
        "import fcntl, os, time\n"
        f"probe = os.open({str(tmp_path / SCRIPT_LOCK_FILE)!r}, os.O_RDONLY)\n"
        "try:\n"
        "    fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB); held = 'free'\n"
        "except BlockingIOError:\n"
        "    held = 'held'\n"
        f"same = os.fstat({SCRIPT_LOCK_FD}).st_ino == os.fstat(probe).st_ino\n"
        f"open({str(marker)!r}, 'w').write(held + ' ' + str(same))\n"
        "time.sleep(2)\n"
    )
    runner = ScriptUpdateRunner(tmp_path, [sys.executable, "-c", code])

    runner.start()

    _wait_for(marker, "held True")
    assert runner.state().state is UpdateState.RUNNING


@pytest.mark.unit
def test_the_script_holds_the_lock_on_its_descriptor_only(tmp_path: Path) -> None:
    """The script closes only that descriptor for the servers it starts: a copy of the lock
    on any other one would outlive the update in them and refuse every next start."""
    marker = tmp_path / "lock-descriptors"
    code = (
        "import os, time\n"
        f"lock = os.stat({str(tmp_path / SCRIPT_LOCK_FILE)!r})\n"
        "held = []\n"
        "for fd in range(256):\n"
        "    try:\n"
        "        info = os.fstat(fd)\n"
        "    except OSError:\n"
        "        continue\n"
        "    if (info.st_dev, info.st_ino) == (lock.st_dev, lock.st_ino):\n"
        "        held.append(fd)\n"
        f"open({str(marker)!r}, 'w').write('fds ' + ' '.join(map(str, held)) + '.')\n"
        "time.sleep(2)\n"
    )
    runner = ScriptUpdateRunner(tmp_path, [sys.executable, "-c", code])

    runner.start()

    _wait_for(marker, ".")
    assert marker.read_text() == f"fds {SCRIPT_LOCK_FD}."


@pytest.mark.unit
def test_failed_state_carries_the_end_of_the_log(tmp_path: Path) -> None:
    (tmp_path / ".pids").mkdir()
    (tmp_path / ".logs").mkdir()
    (tmp_path / STATE_FILE).write_text("failed\n")
    (tmp_path / LOG_FILE).write_text("\n".join(f"line {n}" for n in range(100)))

    progress = ScriptUpdateRunner(tmp_path).state()

    lines = progress.log_tail.splitlines()
    assert progress.state is UpdateState.FAILED
    assert len(lines) == LOG_TAIL_LINES
    assert lines[-1] == "line 99"


@pytest.mark.unit
def test_failed_state_starts_with_the_cause_and_shows_only_the_last_run(tmp_path: Path) -> None:
    (tmp_path / ".pids").mkdir()
    (tmp_path / ".logs").mkdir()
    (tmp_path / STATE_FILE).write_text("failed")
    (tmp_path / ERROR_FILE).write_text("Failed step: make up\n\x1b[31mnpm ERR! network\x1b[0m\n")
    (tmp_path / LOG_FILE).write_text(
        "=== make update 2026-10-01T00:00:00Z ===\nold run\n"
        "=== make update 2026-10-02T00:00:00Z ===\nUpdating to v1.1.0...\n"
        "\x1b[1;33mRolled back to v1.0.0 and started.\x1b[0m\n",
    )

    report = ScriptUpdateRunner(tmp_path).state().log_tail

    assert report == (
        "Failed step: make up\nnpm ERR! network\n\n"
        "=== make update 2026-10-02T00:00:00Z ===\nUpdating to v1.1.0...\n"
        "Rolled back to v1.0.0 and started."
    )


@pytest.mark.unit
def test_start_clears_the_cause_of_the_previous_failure(tmp_path: Path) -> None:
    (tmp_path / ".pids").mkdir()
    (tmp_path / ERROR_FILE).write_text("Failed step: make up")
    runner = ScriptUpdateRunner(tmp_path, [sys.executable, "-c", "pass"])

    runner.start()

    _wait_for_state(runner, UpdateState.FAILED)
    assert "make up" not in runner.state().log_tail


@pytest.mark.unit
def test_the_update_never_waits_for_a_git_password(tmp_path: Path) -> None:
    marker = tmp_path / "env"
    code = (
        "import os, sys\n"
        f"open({str(marker)!r}, 'w').write(os.environ.get('GIT_TERMINAL_PROMPT', '') + ' '"
        " + str(sys.stdin.read() == ''))\n"
    )
    runner = ScriptUpdateRunner(tmp_path, [sys.executable, "-c", code])

    runner.start()

    _wait_for(marker, "0 True")


@pytest.mark.unit
def test_unknown_state_word_counts_as_idle(tmp_path: Path) -> None:
    (tmp_path / ".pids").mkdir()
    (tmp_path / STATE_FILE).write_text("garbage")

    assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.IDLE


@pytest.mark.unit
def test_a_command_that_cannot_start_marks_the_update_failed(tmp_path: Path) -> None:
    runner = ScriptUpdateRunner(tmp_path, ["/nonexistent/command"])

    runner.start()

    _wait_for_state(runner, UpdateState.FAILED)


def _wait_for_state(runner: ScriptUpdateRunner, state: UpdateState) -> None:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if runner.state().state is state:
            return
        time.sleep(0.05)
    pytest.fail(f"the update never became {state}")


@pytest.mark.unit
def test_a_command_that_dies_without_a_state_ends_failed_with_its_log(tmp_path: Path) -> None:
    code = f"open({str(tmp_path / LOG_FILE)!r}, 'a').write('boom\\n')"
    runner = ScriptUpdateRunner(tmp_path, [sys.executable, "-c", code])

    runner.start()

    _wait_for_state(runner, UpdateState.FAILED)
    assert "boom" in runner.state().log_tail
    assert (tmp_path / STATE_FILE).read_text() == "failed"


@pytest.mark.unit
def test_running_without_a_lock_holder_is_failed(tmp_path: Path) -> None:
    (tmp_path / ".pids").mkdir()
    (tmp_path / STATE_FILE).write_text("running")
    (tmp_path / SCRIPT_LOCK_FILE).write_text("12345")

    assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.FAILED


@pytest.mark.unit
def test_running_without_a_lock_file_is_failed(tmp_path: Path) -> None:
    (tmp_path / ".pids").mkdir()
    (tmp_path / STATE_FILE).write_text("running")

    assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.FAILED


@pytest.mark.unit
def test_running_while_the_lock_is_held_stays_running(tmp_path: Path) -> None:
    (tmp_path / ".pids").mkdir()
    (tmp_path / STATE_FILE).write_text("running")
    with (tmp_path / SCRIPT_LOCK_FILE).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.RUNNING


@pytest.mark.unit
def test_start_is_refused_while_an_update_from_the_terminal_holds_the_lock(
    tmp_path: Path,
) -> None:
    (tmp_path / ".pids").mkdir()
    (tmp_path / STATE_FILE).write_text("done")
    with (tmp_path / SCRIPT_LOCK_FILE).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        with pytest.raises(UpdateAlreadyRunningError):
            ScriptUpdateRunner(tmp_path, [sys.executable, "-c", "pass"]).start()


@pytest.mark.unit
def test_start_is_refused_while_the_update_runs(tmp_path: Path) -> None:
    runner = ScriptUpdateRunner(tmp_path, [sys.executable, "-c", "import time; time.sleep(2)"])
    runner.start()

    with pytest.raises(UpdateAlreadyRunningError):
        runner.start()


@pytest.mark.unit
def test_concurrent_starts_spawn_one_process(tmp_path: Path) -> None:
    marker = tmp_path / "spawned"
    code = f"import time; open({str(marker)!r}, 'a').write('x'); time.sleep(2)"
    outcomes: list[bool] = []

    def attempt() -> None:
        try:
            ScriptUpdateRunner(tmp_path, [sys.executable, "-c", code]).start()
            outcomes.append(True)
        except UpdateAlreadyRunningError:
            outcomes.append(False)

    threads = [threading.Thread(target=attempt) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    _wait_for(marker, "x")
    time.sleep(0.3)

    assert outcomes.count(True) == 1
    assert marker.read_text() == "x"


@pytest.mark.unit
def test_the_lock_check_waits_for_the_start_lock(tmp_path: Path) -> None:
    """A terminal run tries its lock under the start lock; the check must not overlap it."""
    (tmp_path / ".pids").mkdir()
    (tmp_path / STATE_FILE).write_text("running")
    checked = threading.Event()

    def check() -> None:
        ScriptUpdateRunner(tmp_path).state()
        checked.set()

    with (tmp_path / START_LOCK_FILE).open("a") as start_lock:
        fcntl.flock(start_lock, fcntl.LOCK_EX)
        thread = threading.Thread(target=check)
        thread.start()
        assert not checked.wait(CHECK_BLOCKED_S)
    thread.join(WAIT_S)

    assert checked.is_set()


def _write(tmp_path: Path, relative_path: str, text: str) -> None:
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.mark.unit
def test_steps_come_from_the_progress_file_in_order(tmp_path: Path) -> None:
    _write(tmp_path, STATE_FILE, "done")
    _write(tmp_path, PROGRESS_FILE, "done\tDownloading v1.2.0\ncurrent\tSaving a backup\n")

    steps = ScriptUpdateRunner(tmp_path).state().steps

    assert steps == (
        UpdateStep("Downloading v1.2.0", UpdateStepStatus.DONE),
        UpdateStep("Saving a backup", UpdateStepStatus.CURRENT),
    )


@pytest.mark.unit
def test_a_failed_update_keeps_its_steps(tmp_path: Path) -> None:
    _write(tmp_path, STATE_FILE, "failed")
    _write(tmp_path, PROGRESS_FILE, "failed\tInstalling v1.2.0\ndone\tRolling back to v1.1.0\n")

    progress = ScriptUpdateRunner(tmp_path).state()

    assert [step.status for step in progress.steps] == [
        UpdateStepStatus.FAILED, UpdateStepStatus.DONE,
    ]


@pytest.mark.unit
def test_without_a_progress_file_there_are_no_steps(tmp_path: Path) -> None:
    assert ScriptUpdateRunner(tmp_path).state().steps == ()


@pytest.mark.unit
@pytest.mark.parametrize("garbled", [
    "done\tDownloading v1.2.0\nhalfway\tSaving a backup\n",
    "done Downloading v1.2.0\n",
    "current\t \n",
])
def test_a_garbled_progress_file_gives_no_steps(tmp_path: Path, garbled: str) -> None:
    _write(tmp_path, STATE_FILE, "done")
    _write(tmp_path, PROGRESS_FILE, garbled)

    assert ScriptUpdateRunner(tmp_path).state().steps == ()
