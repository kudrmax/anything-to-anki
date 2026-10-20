"""ai_proxy must reach the user's Claude login and report why the CLI failed."""
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage
from claude_agent_sdk.types import TextBlock

import ai_proxy

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.unit

AUTH_FAILURE = "Failed to authenticate: OAuth session expired and could not be refreshed"
SDK_WRAPPER_ERROR = "Claude Code returned an error result: success"


async def _expired_login_query(**_: object) -> AsyncIterator[object]:
    """What the SDK yields, then raises, when the CLI's OAuth session has expired."""
    yield AssistantMessage(
        content=[TextBlock(text=AUTH_FAILURE)],
        model="claude-sonnet-4-6",
        error="authentication_failed",
    )
    yield ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=0,
        is_error=True,
        num_turns=1,
        session_id="s",
        result=AUTH_FAILURE,
    )
    raise Exception(SDK_WRAPPER_ERROR)  # noqa: TRY002 — mirrors the SDK's own bare Exception


async def _no_country() -> None:
    return None


async def test_error_names_the_real_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_proxy, "query", _expired_login_query)
    monkeypatch.setattr(ai_proxy, "_get_country", _no_country)

    with pytest.raises(RuntimeError) as exc_info:
        await ai_proxy._generate_structured("system", "user", "claude-sonnet-4-6", {})

    message = str(exc_info.value)
    assert AUTH_FAILURE in message
    assert SDK_WRAPPER_ERROR not in message


def test_usage_names_the_model_an_alias_resolved_to() -> None:
    usage = ai_proxy.UsageInfo.from_sdk(
        {"output_tokens": 50},
        {
            "claude-haiku-5-5": {"outputTokens": 3},
            "claude-sonnet-5-5": {"outputTokens": 50},
        },
    )
    assert usage.model == "claude-sonnet-5-5"


def test_usage_without_model_usage_names_no_model() -> None:
    assert ai_proxy.UsageInfo.from_sdk({}, None).model is None


def test_drops_the_variables_a_claude_session_passed_down() -> None:
    environ = {
        "CLAUDECODE": "1",
        "CLAUDE_CONFIG_DIR": "/Users/me/.claude",
        "ANTHROPIC_BASE_URL": "http://localhost:1",
        "PATH": "/usr/bin",
        "HOME": "/Users/me",
    }

    dropped = ai_proxy.drop_inherited_claude_env(environ)

    assert dropped == ["ANTHROPIC_BASE_URL", "CLAUDECODE", "CLAUDE_CONFIG_DIR"]
    assert environ == {"PATH": "/usr/bin", "HOME": "/Users/me"}


@pytest.mark.parametrize(
    ("stdout", "logged_in"),
    [
        ('{"loggedIn": true, "authMethod": "claude.ai"}', True),
        ('{"loggedIn": false, "authMethod": "none"}', False),
        ("command not found", False),
    ],
)
def test_reads_the_login_from_cli_auth_status(
    monkeypatch: pytest.MonkeyPatch, stdout: str, logged_in: bool,
) -> None:
    def run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        assert args[1:] == ["auth", "status"]
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(ai_proxy.subprocess, "run", run)

    assert ai_proxy.cli_logged_in() is logged_in
