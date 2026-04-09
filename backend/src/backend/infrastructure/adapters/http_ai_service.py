from __future__ import annotations

import httpx

from backend.domain.exceptions import AIServiceError
from backend.domain.ports.ai_service import AIService
from backend.domain.value_objects.batch_meaning_result import BatchMeaningResult
from backend.domain.value_objects.generation_result import GenerationResult


class HttpAIService(AIService):
    """AIService implementation that delegates to a remote AI proxy over HTTP."""

    def __init__(self, url: str, model: str) -> None:
        self._url = url.rstrip("/")
        self._model = model

    def generate_meaning(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        try:
            response = httpx.post(
                f"{self._url}/generate-meaning",
                json={
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                    "model": self._model,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            return GenerationResult(
                meaning=data["meaning"],
                translation=data["translation"],
                synonyms=data["synonyms"],
                ipa=data.get("ipa"),
                tokens_used=data.get("tokens_used", 0),
            )
        except httpx.ConnectError as e:
            raise AIServiceError(
                "Cannot connect to AI proxy. Make sure ai_proxy.py is running on the host."
            ) from e
        except httpx.HTTPStatusError as e:
            detail = e.response.text
            raise AIServiceError(f"AI proxy error: {detail}") from e
        except Exception as e:
            raise AIServiceError(str(e)) from e

    def generate_meanings_batch(
        self, system_prompt: str, user_prompt: str
    ) -> list[BatchMeaningResult]:
        try:
            response = httpx.post(
                f"{self._url}/generate-meanings-batch",
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
            return [
                BatchMeaningResult(
                    word_index=item["word_index"],
                    meaning=item["meaning"],
                    translation=item["translation"],
                    synonyms=item["synonyms"],
                    ipa=item.get("ipa"),
                )
                for item in data["results"]
            ]
        except httpx.ConnectError as e:
            raise AIServiceError(
                "Cannot connect to AI proxy. Make sure ai_proxy.py is running on the host."
            ) from e
        except httpx.HTTPStatusError as e:
            detail = e.response.text
            raise AIServiceError(f"AI proxy error: {detail}") from e
        except Exception as e:
            raise AIServiceError(str(e)) from e
