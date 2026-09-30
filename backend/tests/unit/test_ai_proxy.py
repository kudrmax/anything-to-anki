"""ai_proxy must report why the Claude CLI failed, not the SDK's generic wrapper."""
from __future__ import annotations

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
