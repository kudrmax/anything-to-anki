from __future__ import annotations

import fcntl
import os
import subprocess
import threading
from typing import TYPE_CHECKING

from backend.domain.exceptions import UpdateAlreadyRunningError
from backend.domain.ports.update_runner import UpdateRunner
from backend.domain.value_objects.update_progress import UpdateProgress, UpdateState

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

UPDATE_COMMAND = ("make", "update")
STATE_FILE = ".pids/update.state"
PID_FILE = ".pids/update.pid"
LOCK_FILE = ".pids/update.lock"
LOG_FILE = ".logs/update.log"
LOG_TAIL_LINES = 40


class ScriptUpdateRunner(UpdateRunner):
    """Runs `make update` in the project folder, detached: the script restarts the app, so
    it must outlive it. It reports through the state file, whose one word it ends with. An
    update whose process is gone while the file still says `running` has failed."""

    def __init__(self, project_dir: Path, command: Sequence[str] = UPDATE_COMMAND) -> None:
        self._project_dir = project_dir
        self._command = tuple(command)

    def start(self) -> None:
        state_file = self._project_dir / STATE_FILE
        log_file = self._project_dir / LOG_FILE
        state_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with (self._project_dir / LOCK_FILE).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.state().state is UpdateState.RUNNING:
                raise UpdateAlreadyRunningError
            self._spawn(state_file, log_file)

    def state(self) -> UpdateProgress:
        state = self._read_state()
        if state is UpdateState.RUNNING and not self._runner_alive():
            self._write_state(UpdateState.FAILED)
            state = UpdateState.FAILED
        if state is UpdateState.FAILED:
            return UpdateProgress(state, self._log_tail())
        return UpdateProgress(state)

    def _spawn(self, state_file: Path, log_file: Path) -> None:
        # Until the child is known, this process stands in for it: a start that is cut off
        # here leaves a pid that dies with us, and the update reads as failed.
        self._write_pid(os.getpid())
        state_file.write_text(UpdateState.RUNNING.value, encoding="utf-8")
        try:
            with log_file.open("ab") as log:
                process = subprocess.Popen(  # noqa: S603 — a fixed command, no user input
                    self._command,
                    cwd=self._project_dir,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except OSError:
            self._write_state(UpdateState.FAILED)
            raise
        self._write_pid(process.pid)
        # Reaps the child if it ends while this app lives: a zombie would read as alive.
        threading.Thread(target=process.wait, daemon=True).start()

    def _read_state(self) -> UpdateState:
        try:
            word = (self._project_dir / STATE_FILE).read_text(encoding="utf-8").strip()
            return UpdateState(word)
        except (OSError, ValueError):
            return UpdateState.IDLE

    def _write_state(self, state: UpdateState) -> None:
        (self._project_dir / STATE_FILE).write_text(state.value, encoding="utf-8")

    def _write_pid(self, pid: int) -> None:
        (self._project_dir / PID_FILE).write_text(str(pid), encoding="utf-8")

    def _runner_alive(self) -> bool:
        try:
            pid = int((self._project_dir / PID_FILE).read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
        except (OSError, ValueError) as error:
            return isinstance(error, PermissionError)
        return True

    def _log_tail(self) -> str:
        try:
            text = (self._project_dir / LOG_FILE).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return "\n".join(text.splitlines()[-LOG_TAIL_LINES:])
