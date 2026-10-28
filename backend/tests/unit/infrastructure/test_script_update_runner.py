from __future__ import annotations

import shlex
import subprocess
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
    PID_FILE,
    PROGRESS_FILE,
    STATE_FILE,
    ScriptUpdateRunner,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

WAIT_S = 10
# The fake script's name: the runner knows a running update by it.
SCRIPT = "update.sh"
# Outlives any test: only the test may end it.
LONG_S = 600


def _wait_for(path: Path, text: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if path.exists() and text in path.read_text():
            return
        time.sleep(0.05)
    pytest.fail(f"{path} never got {text!r}")


def _wait_for_state(runner: ScriptUpdateRunner, state: UpdateState) -> None:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if runner.state().state is state:
            return
        time.sleep(0.05)
    pytest.fail(f"the update never became {state}")


def _runner(tmp_path: Path, body: str) -> ScriptUpdateRunner:
    """A runner whose script is `body`. The last line keeps bash itself running the script
    to its end, so the process stays update.sh."""
    (tmp_path / SCRIPT).write_text(f"{body}\n:\n")
    return ScriptUpdateRunner(tmp_path, SCRIPT)


def _python(code: str) -> str:
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"


def _write(tmp_path: Path, relative_path: str, text: str) -> None:
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture()
def terminal_update(tmp_path: Path) -> Iterator[subprocess.Popen[bytes]]:
    """An update started from the terminal: update.sh runs and its pid is in the file."""
    script = subprocess.Popen(["/bin/bash", "-c", f"sleep {LONG_S}; :", SCRIPT])
    _write(tmp_path, PID_FILE, str(script.pid))
    yield script
    script.kill()
    script.wait()


@pytest.mark.unit
def test_without_a_state_file_it_is_idle(tmp_path: Path) -> None:
    assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.IDLE


@pytest.mark.unit
def test_start_writes_running_and_runs_the_script_in_the_project_dir(tmp_path: Path) -> None:
    marker = tmp_path / "cwd"
    runner = _runner(tmp_path, f"pwd > {marker}; sleep 2")

    runner.start()

    assert runner.state().state is UpdateState.RUNNING
    _wait_for(marker, tmp_path.name)


@pytest.mark.unit
def test_the_pid_in_the_file_is_the_scripts_own(tmp_path: Path) -> None:
    marker = tmp_path / "own-pid"
    runner = _runner(tmp_path, f"echo $$ > {marker}; sleep 2")

    runner.start()

    _wait_for(marker, "\n")
    assert (tmp_path / PID_FILE).read_text() == marker.read_text().strip()


@pytest.mark.unit
def test_the_script_gets_none_of_the_apps_open_files(tmp_path: Path) -> None:
    """Whatever the app has open must not outlive it in the servers the update starts."""
    marker = tmp_path / "open-fds"
    code = (
        "import os\n"
        "fds = []\n"
        "for fd in range(3, 256):\n"
        "    try:\n"
        "        os.fstat(fd)\n"
        "    except OSError:\n"
        "        continue\n"
        "    fds.append(fd)\n"
        f"open({str(marker)!r}, 'w').write(str(fds))\n"
    )
    runner = _runner(tmp_path, _python(code))
    with (tmp_path / "held-by-the-app").open("w"):
        runner.start()

        _wait_for(marker, "]")

    assert marker.read_text() == "[]"


@pytest.mark.unit
def test_the_script_writes_nothing_to_the_log_through_the_runner(tmp_path: Path) -> None:
    """The script logs on its own; the runner must not log its output a second time."""
    runner = _runner(tmp_path, "echo twice")

    runner.start()

    _wait_for_state(runner, UpdateState.FAILED)
    log = tmp_path / LOG_FILE
    assert not log.exists() or "twice" not in log.read_text()


@pytest.mark.unit
def test_the_update_never_waits_for_a_git_password(tmp_path: Path) -> None:
    marker = tmp_path / "env"
    code = (
        "import os, sys\n"
        f"open({str(marker)!r}, 'w').write(os.environ.get('GIT_TERMINAL_PROMPT', '') + ' '"
        " + str(sys.stdin.read() == ''))\n"
    )
    runner = _runner(tmp_path, _python(code))

    runner.start()

    _wait_for(marker, "0 True")


@pytest.mark.unit
def test_failed_state_carries_the_end_of_the_log(tmp_path: Path) -> None:
    _write(tmp_path, STATE_FILE, "failed\n")
    _write(tmp_path, LOG_FILE, "\n".join(f"line {n}" for n in range(100)))

    progress = ScriptUpdateRunner(tmp_path).state()

    lines = progress.log_tail.splitlines()
    assert progress.state is UpdateState.FAILED
    assert len(lines) == LOG_TAIL_LINES
    assert lines[-1] == "line 99"


@pytest.mark.unit
def test_failed_state_starts_with_the_cause_and_shows_only_the_last_run(tmp_path: Path) -> None:
    _write(tmp_path, STATE_FILE, "failed")
    _write(tmp_path, ERROR_FILE, "'make up' failed.\n\x1b[31mnpm ERR! network\x1b[0m\n")
    _write(
        tmp_path, LOG_FILE,
        "=== make update 2026-10-01T00:00:00Z ===\nold run\n"
        "=== make update 2026-10-02T00:00:00Z ===\nUpdating to v1.1.0...\n"
        "\x1b[1;33mnpm ERR! network\x1b[0m\n",
    )

    report = ScriptUpdateRunner(tmp_path).state().log_tail

    assert report == (
        "'make up' failed.\nnpm ERR! network\n\n"
        "=== make update 2026-10-02T00:00:00Z ===\nUpdating to v1.1.0...\n"
        "npm ERR! network"
    )


@pytest.mark.unit
def test_start_clears_the_cause_of_the_previous_failure(tmp_path: Path) -> None:
    _write(tmp_path, ERROR_FILE, "'make up' failed.")
    runner = _runner(tmp_path, "true")

    runner.start()

    _wait_for_state(runner, UpdateState.FAILED)
    assert "make up" not in runner.state().log_tail


@pytest.mark.unit
def test_unknown_state_word_counts_as_idle(tmp_path: Path) -> None:
    _write(tmp_path, STATE_FILE, "garbage")

    assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.IDLE


@pytest.mark.unit
def test_a_script_that_cannot_run_marks_the_update_failed(tmp_path: Path) -> None:
    runner = ScriptUpdateRunner(tmp_path, "scripts/missing.sh")

    runner.start()

    _wait_for_state(runner, UpdateState.FAILED)


@pytest.mark.unit
def test_a_script_that_dies_without_a_state_ends_failed_with_its_log(tmp_path: Path) -> None:
    runner = _runner(tmp_path, f"mkdir -p .logs; echo boom >> {LOG_FILE}")

    runner.start()

    _wait_for_state(runner, UpdateState.FAILED)
    assert "boom" in runner.state().log_tail
    assert (tmp_path / STATE_FILE).read_text() == "failed"


@pytest.mark.unit
def test_running_without_a_pid_file_is_failed(tmp_path: Path) -> None:
    _write(tmp_path, STATE_FILE, "running")

    assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.FAILED


@pytest.mark.unit
def test_running_with_a_dead_pid_is_failed(tmp_path: Path) -> None:
    dead = subprocess.Popen(["/bin/bash", "-c", "exit 0", SCRIPT])
    dead.wait()
    _write(tmp_path, STATE_FILE, "running")
    _write(tmp_path, PID_FILE, str(dead.pid))

    assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.FAILED


@pytest.mark.unit
def test_a_pid_another_process_got_since_does_not_count_as_the_update(tmp_path: Path) -> None:
    """After a reboot the old pid may belong to anything; the button must not stay blocked."""
    other = subprocess.Popen(["sleep", str(LONG_S)])
    try:
        _write(tmp_path, STATE_FILE, "running")
        _write(tmp_path, PID_FILE, str(other.pid))

        assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.FAILED
    finally:
        other.kill()
        other.wait()


@pytest.mark.unit
def test_running_while_the_script_lives_stays_running(
    tmp_path: Path, terminal_update: subprocess.Popen[bytes],
) -> None:
    _write(tmp_path, STATE_FILE, "running")

    assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.RUNNING


@pytest.mark.unit
def test_start_is_refused_while_an_update_from_the_terminal_runs(
    tmp_path: Path, terminal_update: subprocess.Popen[bytes],
) -> None:
    _write(tmp_path, STATE_FILE, "running")

    with pytest.raises(UpdateAlreadyRunningError):
        _runner(tmp_path, "true").start()


@pytest.mark.unit
def test_start_is_refused_while_the_update_runs(tmp_path: Path) -> None:
    runner = _runner(tmp_path, "sleep 2")
    runner.start()

    with pytest.raises(UpdateAlreadyRunningError):
        runner.start()


@pytest.mark.unit
def test_concurrent_starts_spawn_one_process(tmp_path: Path) -> None:
    marker = tmp_path / "spawned"
    runner = _runner(tmp_path, f"printf x >> {marker}; sleep 2")
    outcomes: list[bool] = []

    def attempt() -> None:
        try:
            runner.start()
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
def test_a_finished_update_lets_the_next_one_start(tmp_path: Path) -> None:
    marker = tmp_path / "runs"
    runner = _runner(tmp_path, f"printf x >> {marker}; printf done > {STATE_FILE}")

    runner.start()
    _wait_for_state(runner, UpdateState.DONE)
    runner.start()

    _wait_for(marker, "xx")


@pytest.mark.unit
def test_the_commands_to_run_by_hand_go_to_this_copy(tmp_path: Path) -> None:
    copy = tmp_path / "My Copy"
    runner = ScriptUpdateRunner(copy)

    assert runner.restart_command() == f"cd '{copy}' && make down && make up"
    assert runner.update_command() == f"cd '{copy}' && make update"


@pytest.mark.unit
def test_steps_come_from_the_progress_file_in_order(tmp_path: Path) -> None:
    _write(tmp_path, STATE_FILE, "done")
    _write(tmp_path, PROGRESS_FILE, "done\tDownloading v1.2.0\ncurrent\tInstalling v1.2.0\n")

    steps = ScriptUpdateRunner(tmp_path).state().steps

    assert steps == (
        UpdateStep("Downloading v1.2.0", UpdateStepStatus.DONE),
        UpdateStep("Installing v1.2.0", UpdateStepStatus.CURRENT),
    )


@pytest.mark.unit
def test_a_failed_update_keeps_its_steps(tmp_path: Path) -> None:
    _write(tmp_path, STATE_FILE, "failed")
    _write(tmp_path, PROGRESS_FILE, "done\tDownloading v1.2.0\nfailed\tInstalling v1.2.0\n")

    progress = ScriptUpdateRunner(tmp_path).state()

    assert [step.status for step in progress.steps] == [
        UpdateStepStatus.DONE, UpdateStepStatus.FAILED,
    ]


@pytest.mark.unit
def test_without_a_progress_file_there_are_no_steps(tmp_path: Path) -> None:
    assert ScriptUpdateRunner(tmp_path).state().steps == ()


@pytest.mark.unit
@pytest.mark.parametrize("garbled", [
    "done\tDownloading v1.2.0\nhalfway\tInstalling v1.2.0\n",
    "done Downloading v1.2.0\n",
    "current\t \n",
])
def test_a_garbled_progress_file_gives_no_steps(tmp_path: Path, garbled: str) -> None:
    _write(tmp_path, STATE_FILE, "done")
    _write(tmp_path, PROGRESS_FILE, garbled)

    assert ScriptUpdateRunner(tmp_path).state().steps == ()
