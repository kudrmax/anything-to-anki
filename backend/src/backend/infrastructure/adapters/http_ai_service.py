from __future__ import annotations

import logging

import httpx

from backend.domain.exceptions import AIServiceError
from backend.domain.ports.ai_service import AIService
from backend.domain.value_objects.batch_meaning_result import BatchMeaningResult
from backend.domain.value_objects.generation_result import GenerationResult

logger = logging.getLogger(__name__)


class HttpAIService(AIService):
    """AIService implementation that delegates to a remote AI proxy over HTTP."""

    def __init__(self, url: str, model: str) -> None:
        self._url = url.rstrip("/")
        self._model = model

    def generate_meaning(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        endpoint = f"{self._url}/generate-meaning"
        logger.info("http_ai_service: request (endpoint=%s, model=%s)", endpoint, self._model)
        try:
            response = httpx.post(
                endpoint,
                json={
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                    "model": self._model,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            logger.info(
                "http_ai_service: response ok "
                "(endpoint=%s, status=%d, tokens_used=%d)",
                endpoint, response.status_code, data.get("tokens_used", 0),
            )
            return GenerationResult(
                meaning=data["meaning"],
                translation=data["translation"],
                synonyms=data["synonyms"],
                examples=data.get("examples", ""),
                ipa=data.get("ipa"),
                tokens_used=data.get("tokens_used", 0),
            )
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

    def generate_meanings_batch(
        self, system_prompt: str, user_prompt: str
    ) -> list[BatchMeaningResult]:
        endpoint = f"{self._url}/generate-meanings-batch"
        logger.info(
            "http_ai_service: batch request (endpoint=%s, model=%s)", endpoint, self._model,
        )
        try:
            response = httpx.post(
                endpoint,
                json={
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                    "model": self._model,
                },
                # Batch of 15 candidates with 4 output fields (meaning,
                # translation, synonyms, ipa) can take ~5-7 minutes.
                # Worker job_timeout is 600s — keep httpx strictly under
                # it so worker can catch and mark_batch_failed cleanly.
                timeout=540.0,
            )
            response.raise_for_status()
            data = response.json()
            results = [
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
            logger.info(
                "http_ai_service: batch response ok "
                "(endpoint=%s, status=%d, results=%d)",
                endpoint, response.status_code, len(results),
            )
            return results
        except httpx.ConnectError as e:
            logger.exception(
                "http_ai_service: batch connect failed (endpoint=%s)", endpoint,
            )
            raise AIServiceError(
                "Cannot connect to AI proxy. Make sure ai_proxy.py is running on the host."
            ) from e
        except httpx.HTTPStatusError as e:
            detail = e.response.text
            logger.exception(
                "http_ai_service: batch http error "
                "(endpoint=%s, status=%d, detail=%s)",
                endpoint, e.response.status_code, detail[:500],
            )
            raise AIServiceError(f"AI proxy error: {detail}") from e
        except Exception as e:
            logger.exception(
                "http_ai_service: batch unexpected error (endpoint=%s)", endpoint,
            )
            raise AIServiceError(str(e)) from e
