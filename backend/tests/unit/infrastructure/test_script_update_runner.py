from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.update_progress import UpdateState
from backend.infrastructure.adapters.release.script_update_runner import (
    LOG_FILE,
    LOG_TAIL_LINES,
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
    command = [sys.executable, "-c", "import os; print(os.getcwd())"]
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
