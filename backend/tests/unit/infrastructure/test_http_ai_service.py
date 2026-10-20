"""Unit tests for HttpAIService.

Covers the real production AI client used by the backend (talks to ai_proxy
on the host over HTTP). All httpx calls are mocked — no real network.
"""
from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from backend.domain.exceptions import AIServiceError, AIUnavailableError
from backend.domain.ports.ai_outage_recorder import AIOutageRecorder
from backend.domain.ports.ai_usage_recorder import AIUsageRecorder
from backend.domain.value_objects.ai_feature import AIFeature
from backend.domain.value_objects.token_usage import TokenUsage
from backend.infrastructure.adapters.http_ai_service import HttpAIService

if TYPE_CHECKING:
    from backend.domain.entities.ai_usage_record import AIUsageRecord

_MODULE = "backend.infrastructure.adapters.http_ai_service.httpx.post"
_GET = "backend.infrastructure.adapters.http_ai_service.httpx.get"
_BLOCKED = '{"detail":{"message":"Blocked country: RU. Turn on VPN.","vpn_required":true}}'


class FakeUsageRecorder(AIUsageRecorder):
    def __init__(self) -> None:
        self.records: list[AIUsageRecord] = []

    def record(self, record: AIUsageRecord) -> None:
        self.records.append(record)


class FakeOutageRecorder(AIOutageRecorder):
    def __init__(self) -> None:
        self.events: list[tuple[str, bool] | None] = []

    def unavailable(self, reason: str, vpn_required: bool) -> None:
        self.events.append((reason, vpn_required))

    def answered(self) -> None:
        self.events.append(None)


def _service(
    url: str, model: str = "m", usage_recorder: AIUsageRecorder | None = None,
) -> HttpAIService:
    return HttpAIService(
        url=url, model=model, usage_recorder=usage_recorder or FakeUsageRecorder(),
        outage_recorder=FakeOutageRecorder(),
    )


class BrokenUsageRecorder(AIUsageRecorder):
    def record(self, record: AIUsageRecord) -> None:
        raise RuntimeError("database is locked")


_MEANING_PAYLOAD: dict[str, Any] = {
    "meaning": "m",
    "translation": "t",
    "synonyms": "s",
    "ipa": None,
    "usage": {
        "input_tokens": 10,
        "output_tokens": 20,
        "cache_read_tokens": 300,
        "cache_creation_tokens": 4000,
    },
}


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
    resp.json.side_effect = lambda: json.loads(body)
    return httpx.HTTPStatusError("err", request=MagicMock(), response=resp)


def _err_raising_response(exc: BaseException) -> MagicMock:
    """A 'response' whose raise_for_status raises the given exception."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else 500
    resp.json.return_value = {}
    resp.raise_for_status = MagicMock(side_effect=exc)
    return resp


# --- generate_meaning ------------------------------------------------------


@pytest.mark.unit
class TestGenerateMeaning:
    def test_happy_path_returns_parsed_result(self) -> None:
        svc = HttpAIService(
            url="http://proxy:8766", model="claude-sonnet-4-5", usage_recorder=FakeUsageRecorder(),
            outage_recorder=FakeOutageRecorder(),
        )
        payload = {
            "meaning": "to delay",
            "translation": "откладывать",
            "synonyms": "delay, postpone",
            "ipa": "/x/",
            "usage": {"input_tokens": 30, "output_tokens": 12},
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
        svc = _service("http://proxy/")
        with patch(
            _MODULE,
            return_value=_ok_response(
                {
                    "meaning": "m",
                    "translation": "t",
                    "synonyms": "s",
                    "ipa": None,
                    "usage": {"input_tokens": 0},
                }
            ),
        ) as post:
            svc.generate_meaning("s", "u")
        assert post.call_args.args[0] == "http://proxy/generate-meaning"

    def test_missing_ipa_defaults_to_none(self) -> None:
        svc = _service("http://x")
        with patch(
            _MODULE,
            return_value=_ok_response(
                {
                    "meaning": "m",
                    "translation": "t",
                    "synonyms": "s",
                    "usage": {"input_tokens": 1},
                }
            ),
        ):
            result = svc.generate_meaning("s", "u")
        assert result.ipa is None

    def test_missing_usage_defaults_to_zero(self) -> None:
        svc = _service("http://x")
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

    def test_connect_error_means_the_ai_is_unavailable(self) -> None:
        svc = _service("http://x")
        with patch(
            _MODULE, side_effect=httpx.ConnectError("refused")
        ), pytest.raises(AIUnavailableError) as exc:
            svc.generate_meaning("s", "u")
        msg = str(exc.value)
        assert "Cannot connect to AI proxy" in msg
        assert "ai_proxy.py" in msg

    def test_http_status_error_includes_response_body(self) -> None:
        svc = _service("http://x")
        with patch(
            _MODULE,
            return_value=_err_raising_response(_http_status_error(500, "boom")),
        ), pytest.raises(AIServiceError) as exc:
            svc.generate_meaning("s", "u")
        assert "AI proxy error" in str(exc.value)
        assert "boom" in str(exc.value)

    def test_unexpected_exception_wrapped(self) -> None:
        svc = _service("http://x")
        with patch(_MODULE, side_effect=ValueError("oops")), pytest.raises(
            AIServiceError
        ) as exc:
            svc.generate_meaning("s", "u")
        assert "oops" in str(exc.value)


# --- generate_meanings_batch -----------------------------------------------


@pytest.mark.unit
class TestGenerateMeaningsBatch:
    def test_happy_path_parses_multiple_results(self) -> None:
        svc = _service("http://proxy:8766")
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
        svc = _service("http://x")
        with patch(
            _MODULE, return_value=_ok_response({"results": []})
        ) as post:
            svc.generate_meanings_batch("s", "u")
        assert post.call_args.kwargs["timeout"] == 540.0

    def test_empty_results(self) -> None:
        svc = _service("http://x")
        with patch(_MODULE, return_value=_ok_response({"results": []})):
            results = svc.generate_meanings_batch("s", "u")
        assert results == []

    def test_connect_error_raises_proxy_hint(self) -> None:
        svc = _service("http://x")
        with patch(
            _MODULE, side_effect=httpx.ConnectError("refused")
        ), pytest.raises(AIServiceError) as exc:
            svc.generate_meanings_batch("s", "u")
        assert "Cannot connect to AI proxy" in str(exc.value)

    def test_http_status_error_includes_body(self) -> None:
        svc = _service("http://x")
        with patch(
            _MODULE,
            return_value=_err_raising_response(
                _http_status_error(500, "overloaded")
            ),
        ), pytest.raises(AIServiceError) as exc:
            svc.generate_meanings_batch("s", "u")
        assert "AI proxy error" in str(exc.value)
        assert "overloaded" in str(exc.value)

    def test_unexpected_exception_wrapped(self) -> None:
        svc = _service("http://x")
        with patch(_MODULE, side_effect=KeyError("missing")), pytest.raises(
            AIServiceError
        ) as exc:
            svc.generate_meanings_batch("s", "u")
        assert "missing" in str(exc.value)


# --- generate_topic_targets --------------------------------------------------


@pytest.mark.unit
class TestGenerateTopicTargets:
    def test_happy_path_parses_targets(self) -> None:
        svc = _service("http://proxy:8766")
        payload = {
            "targets": [
                {"phrase": "negotiate", "example": "We **negotiate** the offer."},
                {"phrase": "meet halfway", "example": "Let's **meet halfway**."},
            ],
            "usage": {"input_tokens": 120},
        }
        with patch(_MODULE, return_value=_ok_response(payload)) as post:
            result = svc.generate_topic_targets("system", "user")

        assert [(t.phrase, t.example) for t in result] == [
            ("negotiate", "We **negotiate** the offer."),
            ("meet halfway", "Let's **meet halfway**."),
        ]
        assert post.call_args.args[0] == "http://proxy:8766/generate-topic-targets"
        assert post.call_args.kwargs["timeout"] == 540.0

    def test_malformed_response_is_wrapped(self) -> None:
        svc = _service("http://proxy")
        with patch(_MODULE, return_value=_ok_response({"results": []})), pytest.raises(
            AIServiceError
        ):
            svc.generate_topic_targets("s", "u")

    def test_unavailable_ai_keeps_the_reason_the_proxy_gave(self) -> None:
        svc = _service("http://proxy")
        error = _http_status_error(503, _BLOCKED)
        with patch(_MODULE, return_value=_err_raising_response(error)), pytest.raises(
            AIUnavailableError
        ) as exc:
            svc.generate_topic_targets("s", "u")
        assert exc.value.detail == "Blocked country: RU. Turn on VPN."
        assert exc.value.vpn_required

    def test_a_failure_of_this_call_is_not_an_unavailable_ai(self) -> None:
        svc = _service("http://proxy")
        error = _http_status_error(502, '{"detail":"AI call failed: no structured output"}')
        with patch(_MODULE, return_value=_err_raising_response(error)), pytest.raises(
            AIServiceError
        ) as exc:
            svc.generate_topic_targets("s", "u")
        assert not isinstance(exc.value, AIUnavailableError)


# --- usage recording ---------------------------------------------------------


@pytest.mark.unit
class TestUsageRecording:
    def test_tokens_used_counts_cached_tokens_too(self) -> None:
        svc = _service("http://x")
        with patch(_MODULE, return_value=_ok_response(_MEANING_PAYLOAD)):
            result = svc.generate_meaning("s", "u")
        assert result.tokens_used == 4330

    def test_successful_call_is_recorded(self) -> None:
        recorder = FakeUsageRecorder()
        svc = _service("http://x", model="claude-x", usage_recorder=recorder)
        with patch(_MODULE, return_value=_ok_response(_MEANING_PAYLOAD)):
            svc.generate_meaning("s", "u")

        [record] = recorder.records
        assert record.feature is AIFeature.MEANING_SINGLE
        assert record.model == "claude-x"
        assert record.usage == TokenUsage(10, 20, 300, 4000)
        assert record.item_count == 1
        assert record.succeeded
        assert record.duration_ms >= 0
        assert record.created_at.tzinfo is not None

    def test_records_the_model_the_proxy_resolved_an_alias_to(self) -> None:
        recorder = FakeUsageRecorder()
        svc = _service("http://x", model="sonnet", usage_recorder=recorder)
        payload = {**_MEANING_PAYLOAD, "usage": {"input_tokens": 1, "model": "claude-sonnet-5-5"}}
        with patch(_MODULE, return_value=_ok_response(payload)) as post:
            svc.generate_meaning("s", "u")

        assert post.call_args.kwargs["json"]["model"] == "sonnet"
        assert recorder.records[0].model == "claude-sonnet-5-5"

    def test_follow_up_is_recorded_as_its_own_feature(self) -> None:
        recorder = FakeUsageRecorder()
        svc = _service("http://x", usage_recorder=recorder)
        with patch(_MODULE, return_value=_ok_response(_MEANING_PAYLOAD)) as post:
            svc.generate_follow_up("s", "u")

        assert post.call_args.args[0] == "http://x/generate-meaning"
        assert recorder.records[0].feature is AIFeature.MEANING_FOLLOW_UP

    def test_batch_records_how_many_results_came_back(self) -> None:
        recorder = FakeUsageRecorder()
        svc = _service("http://x", usage_recorder=recorder)
        payload = {
            "results": [
                {"phrase_index": 1, "phrase": "a"},
                {"phrase_index": 2, "phrase": "b"},
            ],
            "usage": {"input_tokens": 5},
        }
        with patch(_MODULE, return_value=_ok_response(payload)):
            svc.polish_phrases_batch("s", "u")

        [record] = recorder.records
        assert record.feature is AIFeature.PHRASE_POLISH
        assert record.item_count == 2

    def test_failed_call_is_recorded_without_tokens(self) -> None:
        recorder = FakeUsageRecorder()
        svc = _service("http://x", usage_recorder=recorder)
        error = _http_status_error(502, '{"detail":"AI call failed: boom"}')
        with patch(_MODULE, return_value=_err_raising_response(error)), pytest.raises(
            AIServiceError
        ):
            svc.generate_meanings_batch("s", "u")

        [record] = recorder.records
        assert record.feature is AIFeature.MEANING_BATCH
        assert not record.succeeded
        assert record.usage.total == 0
        assert record.item_count == 0

    @pytest.mark.parametrize("failure", [
        httpx.ConnectError("refused"),
        _http_status_error(503, '{"detail":"Not logged in · Please run /login"}'),
    ])
    def test_a_call_the_ai_never_answered_is_not_recorded(self, failure: Exception) -> None:
        recorder = FakeUsageRecorder()
        svc = _service("http://x", usage_recorder=recorder)
        with patch(_MODULE, return_value=_err_raising_response(failure)), pytest.raises(
            AIUnavailableError
        ):
            svc.generate_meanings_batch("s", "u")

        assert recorder.records == []

    def test_unparsable_answer_keeps_the_tokens_it_cost(self) -> None:
        recorder = FakeUsageRecorder()
        svc = _service("http://x", usage_recorder=recorder)
        payload = {"unexpected": [], "usage": {"input_tokens": 7, "output_tokens": 3}}
        with patch(_MODULE, return_value=_ok_response(payload)), pytest.raises(AIServiceError):
            svc.generate_topic_targets("s", "u")

        [record] = recorder.records
        assert record.feature is AIFeature.TOPIC_TARGETS
        assert not record.succeeded
        assert record.usage.total == 10

    def test_failing_recorder_does_not_lose_the_result(self) -> None:
        svc = _service("http://x", usage_recorder=BrokenUsageRecorder())
        with patch(_MODULE, return_value=_ok_response(_MEANING_PAYLOAD)):
            result = svc.generate_meaning("s", "u")
        assert result.meaning == "m"


# --- outage recording --------------------------------------------------------


@pytest.mark.unit
class TestOutageRecording:
    """Every AI call, whatever feature makes it, keeps the outage everyone sees current."""

    def _svc(self, recorder: FakeOutageRecorder) -> HttpAIService:
        return HttpAIService(
            url="http://x", model="m", usage_recorder=FakeUsageRecorder(),
            outage_recorder=recorder,
        )

    def test_a_blocked_country_is_recorded_as_needing_a_vpn(self) -> None:
        recorder = FakeOutageRecorder()
        error = _http_status_error(503, _BLOCKED)
        with patch(_MODULE, return_value=_err_raising_response(error)), pytest.raises(
            AIUnavailableError
        ):
            self._svc(recorder).generate_meaning("s", "u")

        assert recorder.events == [("Blocked country: RU. Turn on VPN.", True)]

    def test_a_stopped_proxy_is_recorded(self) -> None:
        recorder = FakeOutageRecorder()
        with patch(_MODULE, side_effect=httpx.ConnectError("refused")), pytest.raises(
            AIUnavailableError
        ):
            self._svc(recorder).polish_phrases_batch("s", "u")

        [(reason, vpn_required)] = recorder.events  # type: ignore[misc]
        assert "Cannot connect to AI proxy" in reason
        assert not vpn_required

    @pytest.mark.parametrize("response", [
        _ok_response(_MEANING_PAYLOAD),
        _ok_response({}, status_code=502),
    ])
    def test_any_answer_ends_the_outage(self, response: MagicMock) -> None:
        recorder = FakeOutageRecorder()
        with patch(_MODULE, return_value=response), contextlib.suppress(AIServiceError):
            self._svc(recorder).generate_meaning("s", "u")

        assert recorder.events == [None]

    def test_check_ends_the_outage_when_the_proxy_is_ready(self) -> None:
        recorder = FakeOutageRecorder()
        with patch(_GET, return_value=_ok_response({"available": True})):
            self._svc(recorder).check_available()

        assert recorder.events == [None]

    def test_check_records_why_the_ai_is_unavailable(self) -> None:
        recorder = FakeOutageRecorder()
        response = _ok_response(json.loads(_BLOCKED), status_code=503)
        with patch(_GET, return_value=response), pytest.raises(AIUnavailableError):
            self._svc(recorder).check_available()

        assert recorder.events == [("Blocked country: RU. Turn on VPN.", True)]
