from __future__ import annotations

import os
import re
import shlex
import subprocess
import threading
from typing import TYPE_CHECKING

from backend.domain.exceptions import UpdateAlreadyRunningError
from backend.domain.ports.update_runner import UpdateRunner
from backend.domain.value_objects.update_progress import (
    UpdateProgress,
    UpdateState,
    UpdateStep,
    UpdateStepStatus,
)

if TYPE_CHECKING:
    from pathlib import Path

UPDATE_SCRIPT = "scripts/update.sh"
STATE_FILE = ".pids/update.state"
PID_FILE = ".pids/update.pid"
ERROR_FILE = ".pids/update.error"
# update.sh rewrites it whole on every change: one stage per line, its status, a tab, its
# title.
PROGRESS_FILE = ".pids/update.progress"
PROGRESS_SEPARATOR = "\t"
LOG_FILE = ".logs/update.log"
# Enough of the run's end to see what broke, short enough for the app's popup.
LOG_TAIL_LINES = 40
# update.sh starts every run's log with this.
RUN_HEADER = "=== make update"
# Colours and cursor moves of make and npm output, which a browser shows as garbage.
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# Runs unattended: a git asking for a password would hang the update.
NON_INTERACTIVE = {"GIT_TERMINAL_PROMPT": "0"}


class ScriptUpdateRunner(UpdateRunner):
    """Runs update.sh in the project folder as a process of its own: the script stops and
    restarts the app, so it must outlive it. The script reports through the state file,
    whose one word it ends with.

    The update is running while the process in the pid file is alive and is update.sh;
    a pid file left by a run that died, or whose pid another process got since, does not
    count. The app writes the pid as soon as the script starts; the script writes its own
    when run from the terminal."""

    def __init__(self, project_dir: Path, script: str = UPDATE_SCRIPT) -> None:
        self._project_dir = project_dir
        self._script = script
        # Two clicks at once must not both see the update as not running.
        self._starting = threading.Lock()

    def start(self) -> None:
        with self._starting:
            if self._state().state is UpdateState.RUNNING:
                raise UpdateAlreadyRunningError
            self._spawn()

    def state(self) -> UpdateProgress:
        with self._starting:
            return self._state()

    def restart_command(self) -> str:
        return f"cd {shlex.quote(str(self._project_dir))} && make down && make up"

    def update_command(self) -> str:
        return f"cd {shlex.quote(str(self._project_dir))} && make update"

    def _state(self) -> UpdateProgress:
        state = self._read_state()
        # The script writes its last word before it exits: read again once it is gone.
        if state is UpdateState.RUNNING and not self._script_alive():
            state = self._read_state()
            if state is UpdateState.RUNNING:
                self._write_state(UpdateState.FAILED)
                state = UpdateState.FAILED
        steps = self._steps()
        if state is UpdateState.FAILED:
            return UpdateProgress(state, self._failure_report(), steps)
        return UpdateProgress(state, steps=steps)

    def _spawn(self) -> None:
        (self._project_dir / LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
        self._write_state(UpdateState.RUNNING)
        (self._project_dir / ERROR_FILE).write_text("", encoding="utf-8")
        try:
            process = subprocess.Popen(  # noqa: S603 — a fixed command, no user input
                ["/bin/bash", self._script],
                cwd=self._project_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env={**os.environ, **NON_INTERACTIVE},
            )
        except OSError:
            self._write_state(UpdateState.FAILED)
            raise
        (self._project_dir / PID_FILE).write_text(str(process.pid), encoding="utf-8")
        threading.Thread(target=process.wait, daemon=True).start()

    def _script_alive(self) -> bool:
        try:
            pid = int(self._read(PID_FILE).strip())
        except ValueError:
            return False
        result = subprocess.run(  # noqa: S603 — a fixed command and a number
            ["/bin/ps", "-o", "command=", "-p", str(pid)],
            capture_output=True, text=True, check=False,
        )
        return os.path.basename(self._script) in result.stdout

    def _read_state(self) -> UpdateState:
        try:
            word = (self._project_dir / STATE_FILE).read_text(encoding="utf-8").strip()
            return UpdateState(word)
        except (OSError, ValueError):
            return UpdateState.IDLE

    def _write_state(self, state: UpdateState) -> None:
        (self._project_dir / STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
        (self._project_dir / STATE_FILE).write_text(state.value, encoding="utf-8")

    def _steps(self) -> tuple[UpdateStep, ...]:
        """The stages from the progress file; none when it is missing or garbled."""
        steps = []
        for line in self._read(PROGRESS_FILE).splitlines():
            status, separator, title = line.partition(PROGRESS_SEPARATOR)
            try:
                step_status = UpdateStepStatus(status)
            except ValueError:
                return ()
            if not separator or not title.strip():
                return ()
            steps.append(UpdateStep(title.strip(), step_status))
        return tuple(steps)

    def _failure_report(self) -> str:
        """What broke as the script summed it up, then the end of this run's log."""
        parts = [part for part in (self._read(ERROR_FILE).strip(), self._run_tail()) if part]
        return ANSI_ESCAPE.sub("", "\n\n".join(parts))

    def _run_tail(self) -> str:
        lines = self._read(LOG_FILE).splitlines()
        starts = [index for index, line in enumerate(lines) if line.startswith(RUN_HEADER)]
        run = lines[starts[-1]:] if starts else lines
        return "\n".join(run[-LOG_TAIL_LINES:])

    def _read(self, relative_path: str) -> str:
        try:
            path = self._project_dir / relative_path
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
