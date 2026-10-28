"""The status server update.sh runs while the app is stopped: it answers the page as the
app would, on the system Python, and goes away by itself once the update ends."""
from __future__ import annotations

import fcntl
import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from backend.application.dto.release_dtos import UpdateStateDTO
from backend.infrastructure.adapters.release.script_update_runner import (
    PROGRESS_FILE,
    SCRIPT_LOCK_FILE,
    STATE_FILE,
    ScriptUpdateRunner,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.integration

SERVER = Path(__file__).resolve().parents[3] / "scripts" / "update_status_server.py"
# The interpreter update.sh runs it with: the copy's .venv is replaced during the update.
SYSTEM_PYTHON = "/usr/bin/python3"
HOST = "127.0.0.1"
WAIT_S = 10
PROGRESS = "done\tDownloading v1.2.0\ncurrent\tSaving a backup\npending\tInstalling v1.2.0\n"


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        port: int = probe.getsockname()[1]
        return port


class StatusServer:
    def __init__(self, project_dir: Path) -> None:
        self.port = _free_port()
        self.process = subprocess.Popen(
            [SYSTEM_PYTHON, str(SERVER), "--port", str(self.port), "--host", HOST],
            cwd=project_dir,
        )
        deadline = time.monotonic() + WAIT_S
        while not self.listens():
            assert self.process.poll() is None, "the status server exited"
            assert time.monotonic() < deadline, "the status server never listened"
            time.sleep(0.05)

    def listens(self) -> bool:
        with socket.socket() as probe:
            return probe.connect_ex((HOST, self.port)) == 0

    def get(self, path: str) -> tuple[int, str]:
        try:
            with urllib.request.urlopen(  # noqa: S310 — a local test server
                f"http://{HOST}:{self.port}{path}", timeout=WAIT_S,
            ) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, ""

    def stop(self) -> None:
        self.process.kill()
        self.process.wait(timeout=WAIT_S)


@pytest.fixture()
def project(tmp_path: Path) -> Iterator[Path]:
    (tmp_path / ".pids").mkdir()
    (tmp_path / STATE_FILE).write_text("running")
    (tmp_path / PROGRESS_FILE).write_text(PROGRESS)
    with (tmp_path / SCRIPT_LOCK_FILE).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield tmp_path


@pytest.fixture()
def server(project: Path) -> Iterator[StatusServer]:
    started = StatusServer(project)
    yield started
    started.stop()


def test_state_answers_as_the_app_does(project: Path, server: StatusServer) -> None:
    status, body = server.get("/api/update/state")

    app_answer = UpdateStateDTO.from_progress(ScriptUpdateRunner(project).state())
    assert status == 200
    assert json.loads(body) == app_answer.model_dump()
    assert app_answer.steps[1].status == "current"


def test_state_follows_the_progress_file(project: Path, server: StatusServer) -> None:
    (project / PROGRESS_FILE).write_text("done\tDownloading v1.2.0\n")

    _, body = server.get("/api/update/state")

    assert json.loads(body)["steps"] == [{"title": "Downloading v1.2.0", "status": "done"}]


def test_garbled_progress_gives_no_steps(project: Path, server: StatusServer) -> None:
    (project / PROGRESS_FILE).write_text("halfway\tSaving a backup\n")

    _, body = server.get("/api/update/state")

    assert json.loads(body)["steps"] == []


def test_the_version_and_everything_else_are_unavailable(server: StatusServer) -> None:
    """The page waits for the real server by its version."""
    assert server.get("/api/version")[0] == 503
    assert server.get("/api/updates")[0] == 503


def test_stops_by_itself_once_the_update_lock_is_free(tmp_path: Path) -> None:
    (tmp_path / ".pids").mkdir()
    with (tmp_path / SCRIPT_LOCK_FILE).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        server = StatusServer(tmp_path)
        assert server.process.poll() is None

    assert server.process.wait(timeout=WAIT_S) == 0
    assert not server.listens()
