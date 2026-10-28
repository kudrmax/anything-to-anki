from __future__ import annotations

import os
import sys
import threading
import time
from typing import TYPE_CHECKING

import pytest
from backend.domain.exceptions import UpdateAlreadyRunningError
from backend.domain.value_objects.update_progress import UpdateState
from backend.infrastructure.adapters.release.script_update_runner import (
    LOG_FILE,
    LOG_TAIL_LINES,
    PID_FILE,
    STATE_FILE,
    ScriptUpdateRunner,
)

if TYPE_CHECKING:
    from pathlib import Path

WAIT_S = 10


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
    code = "import os, time; print(os.getcwd(), flush=True); time.sleep(2)"
    command = [sys.executable, "-c", code]
    runner = ScriptUpdateRunner(tmp_path, command)

    runner.start()

    assert runner.state().state is UpdateState.RUNNING
    _wait_for(tmp_path / LOG_FILE, tmp_path.name)


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
def test_unknown_state_word_counts_as_idle(tmp_path: Path) -> None:
    (tmp_path / ".pids").mkdir()
    (tmp_path / STATE_FILE).write_text("garbage")

    assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.IDLE


@pytest.mark.unit
def test_a_command_that_cannot_start_marks_the_update_failed(tmp_path: Path) -> None:
    runner = ScriptUpdateRunner(tmp_path, ["/nonexistent/command"])

    with pytest.raises(OSError):  # noqa: PT011
        runner.start()

    assert runner.state().state is UpdateState.FAILED


def _wait_for_state(runner: ScriptUpdateRunner, state: UpdateState) -> None:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if runner.state().state is state:
            return
        time.sleep(0.05)
    pytest.fail(f"the update never became {state}")


@pytest.mark.unit
def test_a_command_that_dies_without_a_state_ends_failed_with_its_log(tmp_path: Path) -> None:
    command = [sys.executable, "-c", "print('boom', flush=True)"]
    runner = ScriptUpdateRunner(tmp_path, command)

    runner.start()

    _wait_for_state(runner, UpdateState.FAILED)
    assert "boom" in runner.state().log_tail
    assert (tmp_path / STATE_FILE).read_text() == "failed"


@pytest.mark.unit
def test_running_with_a_dead_pid_is_failed(tmp_path: Path) -> None:
    (tmp_path / ".pids").mkdir()
    (tmp_path / STATE_FILE).write_text("running")
    (tmp_path / PID_FILE).write_text("2147483646")

    assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.FAILED


@pytest.mark.unit
def test_running_with_a_live_pid_stays_running(tmp_path: Path) -> None:
    (tmp_path / ".pids").mkdir()
    (tmp_path / STATE_FILE).write_text("running")
    (tmp_path / PID_FILE).write_text(str(os.getpid()))

    assert ScriptUpdateRunner(tmp_path).state().state is UpdateState.RUNNING


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
