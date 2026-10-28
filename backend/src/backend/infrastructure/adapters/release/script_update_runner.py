from __future__ import annotations

import fcntl
import os
import re
import subprocess
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING

from backend.domain.exceptions import UpdateAlreadyRunningError
from backend.domain.ports.update_runner import UpdateRunner
from backend.domain.value_objects.update_progress import UpdateProgress, UpdateState

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

UPDATE_COMMAND = ("make", "update")
STATE_FILE = ".pids/update.state"
PID_FILE = ".pids/update.pid"
START_LOCK_FILE = ".pids/update.lock"
SCRIPT_LOCK_FILE = ".pids/update.script.lock"
ERROR_FILE = ".pids/update.error"
LOG_FILE = ".logs/update.log"
# Enough of the run's end to see the rollback, short enough for the app's popup.
LOG_TAIL_LINES = 40
# update.sh starts every run's log with this.
RUN_HEADER = "=== make update"
# Colours and cursor moves of make and npm output, which a browser shows as garbage.
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# update.sh keeps the lock it finds open on this descriptor instead of taking its own.
SCRIPT_LOCK_FD = 9
# Runs unattended: a git asking for a password would hang the update.
NON_INTERACTIVE = {"GIT_TERMINAL_PROMPT": "0"}


class ScriptUpdateRunner(UpdateRunner):
    """Runs `make update` in the project folder, detached: the script restarts the app, so
    it must outlive it. It reports through the state file, whose one word it ends with.

    The update is running exactly while the flock on the script's lock file is held. This
    runner takes it before the script starts and hands it to the script, which holds it
    to its end: an update whose lock is free while the state says `running` has failed.
    Checking the lock takes it shared for a moment; that happens under the start lock,
    which a script started from the terminal also takes around its own attempt."""

    def __init__(self, project_dir: Path, command: Sequence[str] = UPDATE_COMMAND) -> None:
        self._project_dir = project_dir
        self._command = tuple(command)

    def start(self) -> None:
        (self._project_dir / LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
        with self._start_lock():
            if self._state().state is UpdateState.RUNNING:
                raise UpdateAlreadyRunningError
            script_lock = os.open(
                self._project_dir / SCRIPT_LOCK_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            )
            try:
                try:
                    fcntl.flock(script_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise UpdateAlreadyRunningError from error
                self._spawn(script_lock)
            finally:
                os.close(script_lock)

    def state(self) -> UpdateProgress:
        with self._start_lock():
            return self._state()

    @contextmanager
    def _start_lock(self) -> Iterator[None]:
        (self._project_dir / START_LOCK_FILE).parent.mkdir(parents=True, exist_ok=True)
        with (self._project_dir / START_LOCK_FILE).open("a") as start_lock:
            fcntl.flock(start_lock, fcntl.LOCK_EX)
            yield

    def _state(self) -> UpdateProgress:
        state = self._read_state()
        if state is UpdateState.RUNNING and not self._script_lock_held():
            self._write_state(UpdateState.FAILED)
            state = UpdateState.FAILED
        if state is UpdateState.FAILED:
            return UpdateProgress(state, self._failure_report())
        return UpdateProgress(state)

    def _spawn(self, script_lock: int) -> None:
        self._write_state(UpdateState.RUNNING)
        (self._project_dir / ERROR_FILE).write_text("", encoding="utf-8")
        try:
            process = subprocess.Popen(  # noqa: S603 — a fixed command, no user input
                self._handing_over(script_lock),
                cwd=self._project_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                pass_fds=(script_lock,),
                start_new_session=True,
                env={**os.environ, **NON_INTERACTIVE},
            )
        except OSError:
            self._write_state(UpdateState.FAILED)
            raise
        (self._project_dir / PID_FILE).write_text(str(process.pid), encoding="utf-8")
        threading.Thread(target=process.wait, daemon=True).start()

    def _handing_over(self, script_lock: int) -> list[str]:
        """The command run with the lock moved to the descriptor the script looks at."""
        moves = "" if script_lock == SCRIPT_LOCK_FD else (
            f" {SCRIPT_LOCK_FD}>&{script_lock} {script_lock}>&-"
        )
        return ["/bin/sh", "-c", f'exec "$@"{moves}', "update", *self._command]

    def _script_lock_held(self) -> bool:
        try:
            probe = os.open(self._project_dir / SCRIPT_LOCK_FILE, os.O_RDONLY)
        except FileNotFoundError:
            return False
        try:
            fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        else:
            fcntl.flock(probe, fcntl.LOCK_UN)
            return False
        finally:
            os.close(probe)

    def _read_state(self) -> UpdateState:
        try:
            word = (self._project_dir / STATE_FILE).read_text(encoding="utf-8").strip()
            return UpdateState(word)
        except (OSError, ValueError):
            return UpdateState.IDLE

    def _write_state(self, state: UpdateState) -> None:
        (self._project_dir / STATE_FILE).write_text(state.value, encoding="utf-8")

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
