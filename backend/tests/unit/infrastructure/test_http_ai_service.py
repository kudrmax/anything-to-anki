"""Unit tests for HttpAIService.

Covers the real production AI client used by the backend (talks to ai_proxy
on the host over HTTP). All httpx calls are mocked — no real network.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.domain.exceptions import AIServiceError
from backend.infrastructure.adapters.http_ai_service import HttpAIService

_MODULE = "backend.infrastructure.adapters.http_ai_service.httpx.post"


def _ok_response(json_data: dict[str, Any], status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def _http_status_error(status_code: int, body: str) -> httpx.HTTPStatusError:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = body
    return httpx.HTTPStatusError("err", request=MagicMock(), response=resp)


def _err_raising_response(exc: BaseException) -> MagicMock:
    """A 'response' whose raise_for_status raises the given exception."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 500
    resp.json.return_value = {}
    resp.raise_for_status = MagicMock(side_effect=exc)
    return resp


# --- generate_meaning ------------------------------------------------------


@pytest.mark.unit
class TestGenerateMeaning:
    def test_happy_path_returns_parsed_result(self) -> None:
        svc = HttpAIService(url="http://proxy:8766", model="claude-sonnet-4-5")
        payload = {
            "meaning": "to delay",
            "translation": "откладывать",
            "synonyms": "delay, postpone",
            "ipa": "/x/",
            "tokens_used": 42,
        }
        with patch(_MODULE, return_value=_ok_response(payload)) as post:
            result = svc.generate_meaning("system", "user")

        assert result.meaning == "to delay"
        assert result.translation == "откладывать"
        assert result.synonyms == "delay, postpone"
        assert result.ipa == "/x/"
        assert result.tokens_used == 42

        post.assert_called_once()
        call = post.call_args
        assert call.args[0] == "http://proxy:8766/generate-meaning"
        assert call.kwargs["json"] == {
            "system_prompt": "system",
            "user_prompt": "user",
            "model": "claude-sonnet-4-5",
        }
        assert call.kwargs["timeout"] == 60.0

    def test_strips_trailing_slash_from_url(self) -> None:
        svc = HttpAIService(url="http://proxy/", model="m")
        with patch(
            _MODULE,
            return_value=_ok_response(
                {
                    "meaning": "m",
                    "translation": "t",
                    "synonyms": "s",
                    "ipa": None,
                    "tokens_used": 0,
                }
            ),
        ) as post:
            svc.generate_meaning("s", "u")
        assert post.call_args.args[0] == "http://proxy/generate-meaning"

    def test_missing_ipa_defaults_to_none(self) -> None:
        svc = HttpAIService(url="http://x", model="m")
        with patch(
            _MODULE,
            return_value=_ok_response(
                {
                    "meaning": "m",
                    "translation": "t",
                    "synonyms": "s",
                    "tokens_used": 1,
                }
            ),
        ):
            result = svc.generate_meaning("s", "u")
        assert result.ipa is None

    def test_missing_tokens_used_defaults_to_zero(self) -> None:
        svc = HttpAIService(url="http://x", model="m")
        with patch(
            _MODULE,
            return_value=_ok_response(
                {
                    "meaning": "m",
                    "translation": "t",
                    "synonyms": "s",
                    "ipa": None,
                }
            ),
        ):
            result = svc.generate_meaning("s", "u")
        assert result.tokens_used == 0

    def test_connect_error_raises_proxy_hint(self) -> None:
        svc = HttpAIService(url="http://x", model="m")
        with patch(
            _MODULE, side_effect=httpx.ConnectError("refused")
        ), pytest.raises(AIServiceError) as exc:
            svc.generate_meaning("s", "u")
        msg = str(exc.value)
        assert "Cannot connect to AI proxy" in msg
        assert "ai_proxy.py" in msg

    def test_http_status_error_includes_response_body(self) -> None:
        svc = HttpAIService(url="http://x", model="m")
        with patch(
            _MODULE,
            return_value=_err_raising_response(_http_status_error(500, "boom")),
        ), pytest.raises(AIServiceError) as exc:
            svc.generate_meaning("s", "u")
        assert "AI proxy error" in str(exc.value)
        assert "boom" in str(exc.value)

    def test_unexpected_exception_wrapped(self) -> None:
        svc = HttpAIService(url="http://x", model="m")
        with patch(_MODULE, side_effect=ValueError("oops")), pytest.raises(
            AIServiceError
        ) as exc:
            svc.generate_meaning("s", "u")
        assert "oops" in str(exc.value)


# --- generate_meanings_batch -----------------------------------------------


@pytest.mark.unit
class TestGenerateMeaningsBatch:
    def test_happy_path_parses_multiple_results(self) -> None:
        svc = HttpAIService(url="http://proxy:8766", model="m")
        payload = {
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
                    "ipa": None,
                },
            ]
        }
        with patch(_MODULE, return_value=_ok_response(payload)) as post:
            results = svc.generate_meanings_batch("s", "u")

        assert len(results) == 2
        assert results[0].word_index == 1
        assert results[0].meaning == "m1"
        assert results[0].ipa == "/i1/"
        assert results[1].ipa is None
        assert post.call_args.args[0] == "http://proxy:8766/generate-meanings-batch"

    def test_uses_540s_timeout(self) -> None:
        svc = HttpAIService(url="http://x", model="m")
        with patch(
            _MODULE, return_value=_ok_response({"results": []})
        ) as post:
            svc.generate_meanings_batch("s", "u")
        assert post.call_args.kwargs["timeout"] == 540.0

    def test_empty_results(self) -> None:
        svc = HttpAIService(url="http://x", model="m")
        with patch(_MODULE, return_value=_ok_response({"results": []})):
            results = svc.generate_meanings_batch("s", "u")
        assert results == []

    def test_connect_error_raises_proxy_hint(self) -> None:
        svc = HttpAIService(url="http://x", model="m")
        with patch(
            _MODULE, side_effect=httpx.ConnectError("refused")
        ), pytest.raises(AIServiceError) as exc:
            svc.generate_meanings_batch("s", "u")
        assert "Cannot connect to AI proxy" in str(exc.value)

    def test_http_status_error_includes_body(self) -> None:
        svc = HttpAIService(url="http://x", model="m")
        with patch(
            _MODULE,
            return_value=_err_raising_response(
                _http_status_error(503, "overloaded")
            ),
        ), pytest.raises(AIServiceError) as exc:
            svc.generate_meanings_batch("s", "u")
        assert "AI proxy error" in str(exc.value)
        assert "overloaded" in str(exc.value)

    def test_unexpected_exception_wrapped(self) -> None:
        svc = HttpAIService(url="http://x", model="m")
        with patch(_MODULE, side_effect=KeyError("missing")), pytest.raises(
            AIServiceError
        ) as exc:
            svc.generate_meanings_batch("s", "u")
        assert "missing" in str(exc.value)
