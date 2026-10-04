from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypeVar

import httpx

from backend.domain.entities.ai_usage_record import AIUsageRecord
from backend.domain.exceptions import AIServiceError
from backend.domain.ports.ai_service import AIService
from backend.domain.value_objects.ai_feature import AIFeature
from backend.domain.value_objects.batch_meaning_result import BatchMeaningResult
from backend.domain.value_objects.generation_result import GenerationResult
from backend.domain.value_objects.polished_phrase import PolishedPhrase
from backend.domain.value_objects.token_usage import TokenUsage
from backend.domain.value_objects.topic_target_draft import TopicTargetDraft

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.domain.ports.ai_usage_recorder import AIUsageRecorder

logger = logging.getLogger(__name__)

T = TypeVar("T")

SINGLE_TIMEOUT_SECONDS = 60.0
# Batch of 15 candidates with 4 output fields (meaning, translation, synonyms,
# ipa) can take ~5-7 minutes. Worker job_timeout is 600s — keep httpx strictly
# under it so worker can catch and mark job as failed cleanly.
BATCH_TIMEOUT_SECONDS = 540.0
TOPIC_TIMEOUT_SECONDS = 540.0
POLISH_TIMEOUT_SECONDS = 540.0
MS_PER_SECOND = 1000


class HttpAIService(AIService):
    """AIService implementation that delegates to a remote AI proxy over HTTP.

    Every call, successful or not, is handed to the usage recorder.
    """

    def __init__(self, url: str, model: str, usage_recorder: AIUsageRecorder) -> None:
        self._url = url.rstrip("/")
        self._model = model
        self._usage_recorder = usage_recorder

    def generate_meaning(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        return self._post(
            "generate-meaning", AIFeature.MEANING_SINGLE, system_prompt, user_prompt,
            SINGLE_TIMEOUT_SECONDS, self._parse_meaning,
        )

    def generate_follow_up(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        return self._post(
            "generate-meaning", AIFeature.MEANING_FOLLOW_UP, system_prompt, user_prompt,
            SINGLE_TIMEOUT_SECONDS, self._parse_meaning,
        )

    def generate_meanings_batch(
        self, system_prompt: str, user_prompt: str
    ) -> list[BatchMeaningResult]:
        return self._post(
            "generate-meanings-batch", AIFeature.MEANING_BATCH, system_prompt, user_prompt,
            BATCH_TIMEOUT_SECONDS, self._parse_meanings_batch,
        )

    def polish_phrases_batch(
        self, system_prompt: str, user_prompt: str
    ) -> list[PolishedPhrase]:
        return self._post(
            "polish-phrases-batch", AIFeature.PHRASE_POLISH, system_prompt, user_prompt,
            POLISH_TIMEOUT_SECONDS, self._parse_polished_phrases,
        )

    def generate_topic_targets(
        self, system_prompt: str, user_prompt: str
    ) -> list[TopicTargetDraft]:
        return self._post(
            "generate-topic-targets", AIFeature.TOPIC_TARGETS, system_prompt, user_prompt,
            TOPIC_TIMEOUT_SECONDS, self._parse_topic_targets,
        )

    # Any: the proxy returns JSON whose shape depends on the endpoint;
    # each parser maps it to a typed domain object right away.
    @staticmethod
    def _parse_usage(data: dict[str, Any]) -> TokenUsage:
        raw = data.get("usage") or {}
        return TokenUsage(
            input_tokens=raw.get("input_tokens", 0),
            output_tokens=raw.get("output_tokens", 0),
            cache_read_tokens=raw.get("cache_read_tokens", 0),
            cache_creation_tokens=raw.get("cache_creation_tokens", 0),
        )

    @classmethod
    def _parse_meaning(cls, data: dict[str, Any]) -> GenerationResult:
        return GenerationResult(
            meaning=data["meaning"],
            translation=data["translation"],
            synonyms=data["synonyms"],
            examples=data.get("examples", ""),
            ipa=data.get("ipa"),
            tokens_used=cls._parse_usage(data).total,
        )

    @staticmethod
    def _parse_meanings_batch(data: dict[str, Any]) -> list[BatchMeaningResult]:
        return [
            BatchMeaningResult(
                word_index=item["word_index"],
                meaning=item["meaning"],
                translation=item["translation"],
                synonyms=item["synonyms"],
                examples=item.get("examples", ""),
                ipa=item.get("ipa"),
            )
            for item in data["results"]
        ]

    @staticmethod
    def _parse_polished_phrases(data: dict[str, Any]) -> list[PolishedPhrase]:
        return [
            PolishedPhrase(phrase_index=item["phrase_index"], phrase=item["phrase"])
            for item in data["results"]
        ]

    @staticmethod
    def _parse_topic_targets(data: dict[str, Any]) -> list[TopicTargetDraft]:
        return [
            TopicTargetDraft(phrase=item["phrase"], example=item["example"])
            for item in data["targets"]
        ]

    def _post(
        self,
        path: str,
        feature: AIFeature,
        system_prompt: str,
        user_prompt: str,
        timeout: float,
        parse: Callable[[dict[str, Any]], T],
    ) -> T:
        endpoint = f"{self._url}/{path}"
        logger.info("http_ai_service: request (endpoint=%s, model=%s)", endpoint, self._model)
        started = time.monotonic()
        usage = TokenUsage()
        item_count = 0
        succeeded = False
        try:
            response = httpx.post(
                endpoint,
                json={
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                    "model": self._model,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            usage = self._parse_usage(data)
            result = parse(data)
            item_count = len(result) if isinstance(result, list) else 1
            succeeded = True
            logger.info(
                "http_ai_service: response ok (endpoint=%s, status=%d, tokens_used=%d)",
                endpoint, response.status_code, usage.total,
            )
            return result
        except httpx.ConnectError as e:
            logger.exception("http_ai_service: connect failed (endpoint=%s)", endpoint)
            raise AIServiceError(
                "Cannot connect to AI proxy. Make sure ai_proxy.py is running on the host."
            ) from e
        except httpx.HTTPStatusError as e:
            detail = e.response.text
            logger.exception(
                "http_ai_service: http error (endpoint=%s, status=%d, detail=%s)",
                endpoint, e.response.status_code, detail[:500],
            )
            raise AIServiceError(f"AI proxy error: {detail}") from e
        except Exception as e:
            logger.exception("http_ai_service: unexpected error (endpoint=%s)", endpoint)
            raise AIServiceError(str(e)) from e
        finally:
            self._record(feature, usage, item_count, started, succeeded)

    def _record(
        self,
        feature: AIFeature,
        usage: TokenUsage,
        item_count: int,
        started: float,
        succeeded: bool,
    ) -> None:
        record = AIUsageRecord(
            feature=feature,
            model=self._model,
            usage=usage,
            item_count=item_count,
            duration_ms=round((time.monotonic() - started) * MS_PER_SECOND),
            succeeded=succeeded,
            created_at=datetime.now(tz=UTC),
        )
        # Losing a usage record must not cost the user the AI result it belongs to.
        try:
            self._usage_recorder.record(record)
        except Exception:
            logger.exception("http_ai_service: failed to record usage (feature=%s)", feature)
