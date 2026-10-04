from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypeVar

import httpx

from backend.domain.exceptions import AIServiceError
from backend.domain.ports.ai_service import AIService
from backend.domain.value_objects.batch_meaning_result import BatchMeaningResult
from backend.domain.value_objects.generation_result import GenerationResult
from backend.domain.value_objects.polished_phrase import PolishedPhrase
from backend.domain.value_objects.topic_target_draft import TopicTargetDraft

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")

SINGLE_TIMEOUT_SECONDS = 60.0
# Batch of 15 candidates with 4 output fields (meaning, translation, synonyms,
# ipa) can take ~5-7 minutes. Worker job_timeout is 600s — keep httpx strictly
# under it so worker can catch and mark job as failed cleanly.
BATCH_TIMEOUT_SECONDS = 540.0
TOPIC_TIMEOUT_SECONDS = 540.0
POLISH_TIMEOUT_SECONDS = 540.0


class HttpAIService(AIService):
    """AIService implementation that delegates to a remote AI proxy over HTTP."""

    def __init__(self, url: str, model: str) -> None:
        self._url = url.rstrip("/")
        self._model = model

    def generate_meaning(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        return self._post(
            "generate-meaning", system_prompt, user_prompt, SINGLE_TIMEOUT_SECONDS,
            self._parse_meaning,
        )

    def generate_meanings_batch(
        self, system_prompt: str, user_prompt: str
    ) -> list[BatchMeaningResult]:
        return self._post(
            "generate-meanings-batch", system_prompt, user_prompt, BATCH_TIMEOUT_SECONDS,
            self._parse_meanings_batch,
        )

    def polish_phrases_batch(
        self, system_prompt: str, user_prompt: str
    ) -> list[PolishedPhrase]:
        return self._post(
            "polish-phrases-batch", system_prompt, user_prompt, POLISH_TIMEOUT_SECONDS,
            self._parse_polished_phrases,
        )

    def generate_topic_targets(
        self, system_prompt: str, user_prompt: str
    ) -> list[TopicTargetDraft]:
        return self._post(
            "generate-topic-targets", system_prompt, user_prompt, TOPIC_TIMEOUT_SECONDS,
            self._parse_topic_targets,
        )

    # Any: the proxy returns JSON whose shape depends on the endpoint;
    # each parser maps it to a typed domain object right away.
    @staticmethod
    def _parse_meaning(data: dict[str, Any]) -> GenerationResult:
        return GenerationResult(
            meaning=data["meaning"],
            translation=data["translation"],
            synonyms=data["synonyms"],
            examples=data.get("examples", ""),
            ipa=data.get("ipa"),
            tokens_used=data.get("tokens_used", 0),
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
        system_prompt: str,
        user_prompt: str,
        timeout: float,
        parse: Callable[[dict[str, Any]], T],
    ) -> T:
        endpoint = f"{self._url}/{path}"
        logger.info("http_ai_service: request (endpoint=%s, model=%s)", endpoint, self._model)
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
            result = parse(data)
            logger.info(
                "http_ai_service: response ok (endpoint=%s, status=%d, tokens_used=%d)",
                endpoint, response.status_code, data.get("tokens_used", 0),
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
