"""Answers the page on the copy's port while `make update` has the app stopped, so the page
can show how far the update got.

update.sh starts it after `make down` and stops it before `make up`. It runs on the system
Python with the standard library only: the copy's .venv is being replaced under it. It
also stops by itself once the update's lock is free, so a killed update never leaves it
holding the port.

`GET /api/update/state` answers as the app does, from the same files; anything else is
503, so the page keeps waiting for the real server.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import threading
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE_PATH = "/api/update/state"
STATE_FILE = ".pids/update.state"
PROGRESS_FILE = ".pids/update.progress"
SCRIPT_LOCK_FILE = ".pids/update.script.lock"
PROGRESS_SEPARATOR = "\t"
UPDATE_STATES = ("idle", "running", "failed", "done")
STEP_STATUSES = ("done", "current", "pending", "failed")
IDLE = "idle"
DEFAULT_HOST = "0.0.0.0"  # noqa: S104 — the same address `make up` gives the app


@dataclass(frozen=True)
class Step:
    title: str
    status: str


class UpdateFiles:
    """What update.sh wrote about the run, read the way the app's update runner reads it."""

    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir

    def state_json(self) -> bytes:
        steps = [asdict(step) for step in self._steps()]
        body = {"state": self._state(), "log_tail": "", "steps": steps}
        return json.dumps(body).encode("utf-8")

    def wait_until_update_ends(self) -> None:
        """Blocks while update.sh holds its lock; returns once it is free."""
        with (self._project_dir / SCRIPT_LOCK_FILE).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            fcntl.flock(lock, fcntl.LOCK_UN)

    def _state(self) -> str:
        word = self._read(STATE_FILE).strip()
        return word if word in UPDATE_STATES else IDLE

    def _steps(self) -> list[Step]:
        steps = []
        for line in self._read(PROGRESS_FILE).splitlines():
            status, separator, title = line.partition(PROGRESS_SEPARATOR)
            if status not in STEP_STATUSES or not separator or not title.strip():
                return []
            steps.append(Step(title.strip(), status))
        return steps

    def _read(self, relative_path: str) -> str:
        try:
            return (self._project_dir / relative_path).read_text(
                encoding="utf-8", errors="replace",
            )
        except OSError:
            return ""


def handler_for(files: UpdateFiles) -> type[BaseHTTPRequestHandler]:
    class StatusHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 — the name http.server calls
            if self.path.split("?", 1)[0] == STATE_PATH:
                self._answer(HTTPStatus.OK, files.state_json())
            else:
                self._answer(HTTPStatus.SERVICE_UNAVAILABLE, b"")

        def do_POST(self) -> None:  # noqa: N802 — the name http.server calls
            self._answer(HTTPStatus.SERVICE_UNAVAILABLE, b"")

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            """Polls every two seconds would fill the update log."""

        def _answer(self, status: HTTPStatus, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return StatusHandler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default=DEFAULT_HOST)
    arguments = parser.parse_args()
    files = UpdateFiles(Path.cwd())
    server = ThreadingHTTPServer((arguments.host, arguments.port), handler_for(files))
    server.daemon_threads = True

    def stop_when_the_update_ends() -> None:
        files.wait_until_update_ends()
        server.shutdown()

    threading.Thread(target=stop_when_the_update_ends, daemon=True).start()
    server.serve_forever()
    server.server_close()


if __name__ == "__main__":
    main()
