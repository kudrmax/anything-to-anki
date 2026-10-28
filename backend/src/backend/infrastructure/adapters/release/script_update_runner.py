from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from backend.domain.ports.update_runner import UpdateRunner
from backend.domain.value_objects.update_progress import UpdateProgress, UpdateState

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

UPDATE_COMMAND = ("make", "update")
STATE_FILE = ".pids/update.state"
LOG_FILE = ".logs/update.log"
LOG_TAIL_LINES = 40


class ScriptUpdateRunner(UpdateRunner):
    """Runs `make update` in the project folder, detached: the script restarts the app, so
    it must outlive it. It reports through the state file, whose one word it ends with."""

    def __init__(self, project_dir: Path, command: Sequence[str] = UPDATE_COMMAND) -> None:
        self._project_dir = project_dir
        self._command = tuple(command)

    def start(self) -> None:
        state_file = self._project_dir / STATE_FILE
        log_file = self._project_dir / LOG_FILE
        state_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(UpdateState.RUNNING.value, encoding="utf-8")
        try:
            with log_file.open("ab") as log:
                subprocess.Popen(  # noqa: S603 — a fixed command, no user input
                    self._command,
                    cwd=self._project_dir,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except OSError:
            state_file.write_text(UpdateState.FAILED.value, encoding="utf-8")
            raise

    def state(self) -> UpdateProgress:
        state = self._read_state()
        if state is UpdateState.FAILED:
            return UpdateProgress(state, self._log_tail())
        return UpdateProgress(state)

    def _read_state(self) -> UpdateState:
        try:
            word = (self._project_dir / STATE_FILE).read_text(encoding="utf-8").strip()
            return UpdateState(word)
        except (OSError, ValueError):
            return UpdateState.IDLE

    def _log_tail(self) -> str:
        try:
            text = (self._project_dir / LOG_FILE).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return "\n".join(text.splitlines()[-LOG_TAIL_LINES:])
