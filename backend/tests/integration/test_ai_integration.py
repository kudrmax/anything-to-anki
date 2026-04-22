"""End-to-end integration tests for the AI pipeline.

These tests verify the FULL chain that runs in production:

    HttpAIService (backend in Docker)
        → HTTP POST →
    ai_proxy.py (host process)
        → claude_agent_sdk →
    Claude API
        → structured JSON →
    ai_proxy.py
        → HTTP response →
    HttpAIService → GenerationResult / BatchMeaningResult

**Why this exists:** production has had connectivity and contract-mismatch
issues between the Docker container and ai_proxy that were invisible to
unit tests (which mock httpx). These tests catch:
- JSON schema drift between ai_proxy responses and HttpAIService parsing
- ai_proxy startup / import failures
- claude_agent_sdk auth issues (Keychain, CLI path)
- Timeout mismatches
- Network connectivity (host.docker.internal equivalent)

**How to run:**
    make test-ai                          # via Makefile
    pytest -m ai_integration -v           # directly
    pytest -m ai_integration -k single    # just single-meaning test
    pytest -m ai_integration -k batch     # just batch test

**Requirements:**
- claude CLI installed and authenticated (`claude` in PATH)
- ai_proxy dependencies installed (claude-agent-sdk, fastapi, uvicorn)
- Internet access (calls real Claude API)

**Cost:** each test makes 1 real API call. ~5-30s per test, ~0.01$ per run.
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from backend.domain.value_objects.batch_meaning_result import BatchMeaningResult
from backend.domain.value_objects.generation_result import GenerationResult
from backend.infrastructure.adapters.http_ai_service import HttpAIService

# ai_proxy.py lives at repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_AI_PROXY_SCRIPT = _REPO_ROOT / "ai_proxy.py"

# Use venv that has claude-agent-sdk installed.
# Priority: .venv-ai-proxy (dedicated) → .venv (dev, if sdk installed there)
_AI_VENV = _REPO_ROOT / ".venv-ai-proxy"
_DEV_VENV = _REPO_ROOT / ".venv"


def _find_python() -> str:
    """Find a Python with claude-agent-sdk available."""
    for venv in [_AI_VENV, _DEV_VENV]:
        py = venv / "bin" / "python"
        if py.exists():
            # Quick check: can it import claude_agent_sdk?
            result = subprocess.run(
                [str(py), "-c", "import claude_agent_sdk"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                return str(py)
    pytest.skip(
        "No Python venv with claude-agent-sdk found. "
        "Need .venv-ai-proxy or .venv with 'pip install claude-agent-sdk'."
    )
    return ""  # unreachable, keeps mypy happy


def _free_port() -> int:
    """Find an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _localhost_client() -> httpx.Client:
    """httpx client that bypasses any proxy for localhost connections."""
    return httpx.Client(proxy=None, trust_env=False)


def _wait_for_ready(url: str, timeout: float = 30.0) -> None:
    """Poll the health endpoint until ai_proxy is ready."""
    deadline = time.monotonic() + timeout
    with _localhost_client() as client:
        while time.monotonic() < deadline:
            try:
                resp = client.get(f"{url}/health", timeout=2.0)
                if resp.status_code == 200:
                    return
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(0.5)
    raise RuntimeError(f"ai_proxy did not become ready within {timeout}s at {url}")


def _env_without_proxy() -> dict[str, str]:
    """Return a copy of os.environ with proxy vars cleared for localhost."""
    env = os.environ.copy()
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
                "all_proxy", "ALL_PROXY"):
        env.pop(key, None)
    env["NO_PROXY"] = "127.0.0.1,localhost"
    return env


@pytest.fixture(scope="module", autouse=True)
def _clear_proxy_for_tests() -> Any:
    """Temporarily unset proxy env vars so httpx (inside HttpAIService)
    doesn't try to route localhost traffic through a corporate SOCKS proxy."""
    saved: dict[str, str | None] = {}
    proxy_keys = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
                  "all_proxy", "ALL_PROXY")
    for key in proxy_keys:
        saved[key] = os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    yield
    for key, val in saved.items():
        if val is not None:
            os.environ[key] = val
        else:
            os.environ.pop(key, None)
    os.environ.pop("NO_PROXY", None)


@pytest.fixture(scope="module")
def ai_proxy_url() -> str:
    """Start ai_proxy.py on a random port, yield the base URL, tear down after."""
    if not _AI_PROXY_SCRIPT.exists():
        pytest.skip(f"ai_proxy.py not found at {_AI_PROXY_SCRIPT}")

    python = _find_python()
    port = _free_port()
    url = f"http://127.0.0.1:{port}"

    env = _env_without_proxy()
    env["PYTHONPATH"] = str(_REPO_ROOT / "backend" / "src")

    proc = subprocess.Popen(
        [python, str(_AI_PROXY_SCRIPT), "--port", str(port)],
        cwd=str(_REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        _wait_for_ready(url)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.fixture(scope="module")
def local_client() -> httpx.Client:
    """httpx client that skips proxy for localhost calls in tests."""
    with _localhost_client() as client:
        yield client


@pytest.fixture()
def ai_service(ai_proxy_url: str) -> HttpAIService:
    """HttpAIService pointed at the test ai_proxy instance."""
    return HttpAIService(url=ai_proxy_url, model="claude-haiku-4-5-20251001")


# --- Health / connectivity -------------------------------------------------


@pytest.mark.ai_integration
def test_ai_proxy_health_endpoint(
    ai_proxy_url: str, local_client: httpx.Client
) -> None:
    """Verify ai_proxy is up and /health returns 200."""
    resp = local_client.get(f"{ai_proxy_url}/health", timeout=5.0)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# --- Single meaning generation ----------------------------------------------


@pytest.mark.ai_integration
def test_single_meaning_full_roundtrip(ai_service: HttpAIService) -> None:
    """Full round-trip: HttpAIService → ai_proxy → Claude API → response.

    Verifies:
    - HTTP connectivity (no ConnectError)
    - JSON contract matches (ai_proxy response parses into GenerationResult)
    - All required fields are non-empty strings
    - tokens_used is a positive integer (confirms usage tracking works)
    """
    system_prompt = (
        "You are a vocabulary assistant. "
        "Explain the word briefly. Translate to Russian. "
        "Give 2 synonyms. Give IPA transcription."
    )
    user_prompt = 'Word: "procrastinate" (VERB)\nContext: "I tend to procrastinate on important tasks."'

    result = ai_service.generate_meaning(system_prompt, user_prompt)

    # Type check — if JSON contract drifted, this would fail at parsing
    assert isinstance(result, GenerationResult)

    # All fields populated
    assert isinstance(result.meaning, str) and len(result.meaning) > 0
    assert isinstance(result.translation, str) and len(result.translation) > 0
    assert isinstance(result.synonyms, str) and len(result.synonyms) > 0
    # IPA may be None in edge cases but should normally be present
    assert result.ipa is None or (isinstance(result.ipa, str) and len(result.ipa) > 0)

    # Token accounting works end-to-end
    assert isinstance(result.tokens_used, int)
    assert result.tokens_used > 0


# --- Batch meaning generation -----------------------------------------------


@pytest.mark.ai_integration
def test_batch_meanings_full_roundtrip(ai_service: HttpAIService) -> None:
    """Full round-trip for batch generation (the production hot path).

    Verifies:
    - Batch endpoint works (/generate-meanings-batch)
    - Multiple results come back with correct word_index mapping
    - JSON contract: list[BatchMeaningResult] parses correctly
    - Each result has non-empty content
    """
    system_prompt = (
        "You are a vocabulary assistant. "
        "For each word, provide meaning (explain briefly), "
        "translation (Russian, 1-3 words), "
        "synonyms (2-3 English synonyms), "
        "and IPA transcription."
    )
    user_prompt = (
        'Word 1: Word: "elaborate" (VERB)\n'
        'Context: "Could you elaborate on that point?"\n\n'
        'Word 2: Word: "reluctant" (ADJ)\n'
        'Context: "She was reluctant to leave."'
    )

    results = ai_service.generate_meanings_batch(system_prompt, user_prompt)

    # Type check
    assert isinstance(results, list)
    assert len(results) == 2
    for r in results:
        assert isinstance(r, BatchMeaningResult)

    # word_index mapping is correct (1-based as sent in prompt)
    indexes = {r.word_index for r in results}
    assert indexes == {1, 2}

    # Content is populated
    for r in results:
        assert isinstance(r.meaning, str) and len(r.meaning) > 0
        assert isinstance(r.translation, str) and len(r.translation) > 0
        assert isinstance(r.synonyms, str) and len(r.synonyms) > 0


# --- Error handling ---------------------------------------------------------


@pytest.mark.ai_integration
def test_ai_proxy_returns_502_on_bad_model(ai_proxy_url: str) -> None:
    """Sending an invalid model name should result in a clear error from
    ai_proxy, not a hang or cryptic 500. HttpAIService wraps it as
    AIServiceError."""
    from backend.domain.exceptions import AIServiceError

    svc = HttpAIService(url=ai_proxy_url, model="nonexistent-model-xyz-999")
    with pytest.raises(AIServiceError) as exc_info:
        svc.generate_meaning("system", "user prompt")

    # The error should contain something useful, not just "500"
    assert len(str(exc_info.value)) > 20


# --- Contract validation (no AI call needed) --------------------------------


