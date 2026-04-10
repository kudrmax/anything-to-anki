"""Unit tests for ClaudeAIService.

NOTE: ClaudeAIService is dead code in the current architecture (backend uses
HttpAIService → ai_proxy on host). See tasks/dead-code-claude-ai-service.md.
These tests document the expected error-handling behavior in case the module
is ever revived; they also bring the file from 0% to ~90%+ coverage.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.domain.exceptions import AIServiceError
from backend.infrastructure.adapters.claude_ai_service import ClaudeAIService


# --- helpers ---------------------------------------------------------------


class _FakeResultMessage:
    """Stand-in for claude_agent_sdk.ResultMessage.

    The production code does ``isinstance(message, ResultMessage)`` against the
    symbol imported into the module, so we patch that symbol to point at this
    class for the duration of each test.
    """

    def __init__(
        self,
        structured_output: Any = None,
        usage: dict[str, int] | None = None,
    ) -> None:
        self.structured_output = structured_output
        self.usage = usage


def _async_iter(items: list[Any]) -> AsyncIterator[Any]:
    async def _gen() -> AsyncIterator[Any]:
        for item in items:
            yield item

    return _gen()


def _patch_query_yields(messages: list[Any]) -> Any:
    """Patch ``query`` so it returns an async iterator over the given messages."""

    def _fake_query(prompt: str, options: Any) -> AsyncIterator[Any]:
        return _async_iter(messages)

    return patch(
        "backend.infrastructure.adapters.claude_ai_service.query",
        side_effect=_fake_query,
    )


def _patch_query_raises(exc: BaseException) -> Any:
    """Patch ``query`` so calling it raises the given exception synchronously
    when iterated."""

    def _fake_query(prompt: str, options: Any) -> AsyncIterator[Any]:
        async def _raiser() -> AsyncIterator[Any]:
            raise exc
            yield  # pragma: no cover - unreachable, makes _raiser an async gen

        return _raiser()

    return patch(
        "backend.infrastructure.adapters.claude_ai_service.query",
        side_effect=_fake_query,
    )


def _patch_query_call_raises(exc: BaseException) -> Any:
    """Patch ``query`` so even *calling* it raises (CLINotFoundError etc are
    raised by the SDK before any iteration starts)."""
    return patch(
        "backend.infrastructure.adapters.claude_ai_service.query",
        side_effect=exc,
    )


@pytest.fixture
def patched_result_message() -> Any:
    with patch(
        "backend.infrastructure.adapters.claude_ai_service.ResultMessage",
        _FakeResultMessage,
    ):
        yield


@pytest.fixture
def service() -> ClaudeAIService:
    return ClaudeAIService(model="claude-sonnet-4-5")


# --- single generation -----------------------------------------------------


@pytest.mark.unit
def test_generate_meaning_happy_path_dict_structured(
    service: ClaudeAIService, patched_result_message: None
) -> None:
    msg = _FakeResultMessage(
        structured_output={
            "meaning": "to delay",
            "translation": "откладывать",
            "synonyms": "delay, postpone",
            "ipa": "/prəˈkræs.tɪ.neɪt/",
        },
        usage={"input_tokens": 100, "output_tokens": 50},
    )
    with _patch_query_yields([msg]):
        result = service.generate_meaning("system", "user")

    assert result.meaning == "to delay"
    assert result.translation == "откладывать"
    assert result.synonyms == "delay, postpone"
    assert result.ipa == "/prəˈkræs.tɪ.neɪt/"
    assert result.tokens_used == 150


@pytest.mark.unit
def test_generate_meaning_happy_path_json_string_structured(
    service: ClaudeAIService, patched_result_message: None
) -> None:
    payload = {
        "meaning": "to delay",
        "translation": "откладывать",
        "synonyms": "delay",
        "ipa": "/x/",
    }
    msg = _FakeResultMessage(
        structured_output=json.dumps(payload),
        usage={"input_tokens": 10, "output_tokens": 5},
    )
    with _patch_query_yields([msg]):
        result = service.generate_meaning("system", "user")

    assert result.meaning == "to delay"
    assert result.tokens_used == 15


@pytest.mark.unit
def test_generate_meaning_no_structured_output_raises(
    service: ClaudeAIService, patched_result_message: None
) -> None:
    msg = _FakeResultMessage(structured_output=None, usage={})
    with _patch_query_yields([msg]), pytest.raises(AIServiceError) as exc:
        service.generate_meaning("s", "u")
    assert "No structured output" in str(exc.value)


@pytest.mark.unit
def test_generate_meaning_cli_not_found_wraps_in_ai_service_error(
    service: ClaudeAIService,
) -> None:
    """When ``query`` raises CLINotFoundError, it propagates out as AIServiceError.

    NOTE: the outer ``except CLINotFoundError`` branch in ``generate_meaning``
    that adds the install hint is unreachable because ``_async_generate``'s
    inner ``except Exception`` catches everything first and wraps it as
    AIServiceError. See tasks/dead-code-claude-ai-service.md for details.
    """
    from claude_agent_sdk import CLINotFoundError

    err = CLINotFoundError("not found")
    with _patch_query_call_raises(err), pytest.raises(AIServiceError) as exc:
        service.generate_meaning("s", "u")
    assert "not found" in str(exc.value)


@pytest.mark.unit
def test_generate_meaning_cli_connection_error_wraps_in_ai_service_error(
    service: ClaudeAIService,
) -> None:
    """See note above re: dead error-mapping branches."""
    from claude_agent_sdk import CLIConnectionError

    err = CLIConnectionError("nope")
    with _patch_query_call_raises(err), pytest.raises(AIServiceError) as exc:
        service.generate_meaning("s", "u")
    assert "nope" in str(exc.value)


@pytest.mark.unit
def test_generate_meaning_process_error_wraps_in_ai_service_error(
    service: ClaudeAIService,
) -> None:
    """See note above re: dead error-mapping branches."""
    from claude_agent_sdk import ProcessError

    err = ProcessError("died", exit_code=2)
    with _patch_query_call_raises(err), pytest.raises(AIServiceError) as exc:
        service.generate_meaning("s", "u")
    # The default ProcessError str includes the exit code; we just verify the
    # underlying message is preserved through the wrap.
    assert "died" in str(exc.value)


@pytest.mark.unit
def test_generate_meaning_inner_auth_keyword_raises_auth_hint(
    service: ClaudeAIService,
) -> None:
    """An exception during iteration whose detail mentions 'authentication'
    should be wrapped with the 'Not authenticated' hint."""
    err = RuntimeError("authentication failed: token expired")
    with _patch_query_raises(err), pytest.raises(AIServiceError) as exc:
        service.generate_meaning("s", "u")
    assert "Not authenticated" in str(exc.value)


@pytest.mark.unit
def test_generate_meaning_inner_generic_exception_passes_through_detail(
    service: ClaudeAIService,
) -> None:
    err = RuntimeError("disk full")
    with _patch_query_raises(err), pytest.raises(AIServiceError) as exc:
        service.generate_meaning("s", "u")
    detail = str(exc.value)
    assert "disk full" in detail
    assert "Not authenticated" not in detail


# --- batch generation ------------------------------------------------------


@pytest.mark.unit
def test_generate_meanings_batch_happy_path(
    service: ClaudeAIService, patched_result_message: None
) -> None:
    msg = _FakeResultMessage(
        structured_output={
            "results": [
                {
                    "word_index": 1,
                    "meaning": "m1",
                    "translation": "t1",
                    "synonyms": "s1",
                    "ipa": "/i1/",
                },
                {
                    "word_index": 2,
                    "meaning": "m2",
                    "translation": "t2",
                    "synonyms": "s2",
                    "ipa": "/i2/",
                },
            ]
        }
    )
    with _patch_query_yields([msg]):
        results = service.generate_meanings_batch("s", "u")

    assert len(results) == 2
    assert results[0].word_index == 1
    assert results[0].meaning == "m1"
    assert results[1].word_index == 2
    assert results[1].ipa == "/i2/"


@pytest.mark.unit
def test_generate_meanings_batch_accepts_json_string(
    service: ClaudeAIService, patched_result_message: None
) -> None:
    payload = {
        "results": [
            {
                "word_index": 1,
                "meaning": "m",
                "translation": "t",
                "synonyms": "s",
                "ipa": None,
            }
        ]
    }
    msg = _FakeResultMessage(structured_output=json.dumps(payload))
    with _patch_query_yields([msg]):
        results = service.generate_meanings_batch("s", "u")
    assert len(results) == 1
    assert results[0].ipa is None


@pytest.mark.unit
def test_generate_meanings_batch_no_structured_output_raises(
    service: ClaudeAIService, patched_result_message: None
) -> None:
    msg = _FakeResultMessage(structured_output=None)
    with _patch_query_yields([msg]), pytest.raises(AIServiceError) as exc:
        service.generate_meanings_batch("s", "u")
    assert "No structured output" in str(exc.value)


@pytest.mark.unit
def test_generate_meanings_batch_cli_not_found_wraps_in_ai_service_error(
    service: ClaudeAIService,
) -> None:
    """See note in single-generation tests re: dead error-mapping branches."""
    from claude_agent_sdk import CLINotFoundError

    with _patch_query_call_raises(CLINotFoundError("nf")), pytest.raises(
        AIServiceError
    ) as exc:
        service.generate_meanings_batch("s", "u")
    assert "nf" in str(exc.value)


@pytest.mark.unit
def test_generate_meanings_batch_cli_connection_error_wraps(
    service: ClaudeAIService,
) -> None:
    from claude_agent_sdk import CLIConnectionError

    with _patch_query_call_raises(CLIConnectionError("nope")), pytest.raises(
        AIServiceError
    ) as exc:
        service.generate_meanings_batch("s", "u")
    assert "nope" in str(exc.value)


@pytest.mark.unit
def test_generate_meanings_batch_process_error_wraps(
    service: ClaudeAIService,
) -> None:
    from claude_agent_sdk import ProcessError

    with _patch_query_call_raises(
        ProcessError("died", exit_code=7)
    ), pytest.raises(AIServiceError) as exc:
        service.generate_meanings_batch("s", "u")
    assert "died" in str(exc.value)


@pytest.mark.unit
def test_generate_meanings_batch_auth_error_raises_auth_hint(
    service: ClaudeAIService,
) -> None:
    err = RuntimeError("Not logged in")
    with _patch_query_raises(err), pytest.raises(AIServiceError) as exc:
        service.generate_meanings_batch("s", "u")
    assert "Not authenticated" in str(exc.value)


@pytest.mark.unit
def test_generate_meanings_batch_generic_error_passes_through_detail(
    service: ClaudeAIService,
) -> None:
    err = RuntimeError("kaboom")
    with _patch_query_raises(err), pytest.raises(AIServiceError) as exc:
        service.generate_meanings_batch("s", "u")
    assert "kaboom" in str(exc.value)


# --- model passthrough -----------------------------------------------------


@pytest.mark.unit
def test_constructor_stores_model() -> None:
    svc = ClaudeAIService(model="claude-opus-4-6")
    assert svc._model == "claude-opus-4-6"  # noqa: SLF001 - intentional white-box assertion
