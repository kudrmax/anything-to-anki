from __future__ import annotations

import asyncio
import json
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from claude_agent_sdk import CLIConnectionError, CLINotFoundError, ProcessError

from backend.domain.exceptions import AIServiceError
from backend.domain.ports.ai_service import AIService
from backend.domain.value_objects.batch_meaning_result import BatchMeaningResult
from backend.domain.value_objects.generation_result import GenerationResult

_SINGLE_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "meaning": {"type": "string"},
            "ipa": {"type": "string"},
        },
        "required": ["meaning", "ipa"],
    },
}

_BATCH_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "lemma": {"type": "string"},
                        "pos": {"type": "string"},
                        "meaning": {"type": "string"},
                        "ipa": {"type": "string"},
                    },
                    "required": ["lemma", "pos", "meaning", "ipa"],
                },
            }
        },
        "required": ["results"],
    },
}


class ClaudeAIService(AIService):
    """AIService implementation backed by Claude via claude-agent-sdk (CLI auth).

    generate_meaning() is synchronous and must be called from a thread
    (e.g. via asyncio.to_thread) so that asyncio.run() can create a fresh
    event loop without conflicting with the FastAPI event loop.
    """

    def __init__(self, model: str) -> None:
        self._model = model

    # --- single generation ---------------------------------------------------

    def generate_meaning(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        try:
            return asyncio.run(self._async_generate(system_prompt, user_prompt))
        except AIServiceError:
            raise
        except CLINotFoundError as e:
            raise AIServiceError("Claude Code CLI not found. Install it at https://claude.ai/download") from e
        except CLIConnectionError as e:
            raise AIServiceError("Cannot connect to Claude. Run 'claude' to log in.") from e
        except ProcessError as e:
            raise AIServiceError(f"Claude process failed (exit {e.exit_code}). Run 'claude' to check auth.") from e
        except Exception as e:
            raise AIServiceError(str(e)) from e

    async def _async_generate(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        stderr_lines: list[str] = []

        options = ClaudeAgentOptions(
            model=self._model,
            system_prompt=system_prompt,
            max_turns=1,
            output_format=_SINGLE_SCHEMA,
            stderr=stderr_lines.append,
        )
        tokens_used = 0
        structured: dict[str, Any] | None = None
        try:
            async for message in query(prompt=user_prompt, options=options):
                if isinstance(message, ResultMessage):
                    usage = message.usage or {}
                    tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    structured = message.structured_output
        except Exception as e:
            stderr_detail = " | ".join(stderr_lines).strip()
            detail = stderr_detail or str(e)
            if "authentication" in detail.lower() or "login" in detail.lower() or "not logged" in detail.lower():
                raise AIServiceError(f"Not authenticated. Run 'claude' to log in. ({detail})") from e
            raise AIServiceError(detail) from e

        if structured is None:
            raise AIServiceError("No structured output received from Claude")

        # structured_output may arrive as a JSON string or a dict
        if isinstance(structured, str):
            structured = json.loads(structured)  # type: ignore[assignment]

        return GenerationResult(
            meaning=structured["meaning"],  # type: ignore[index]
            ipa=structured.get("ipa"),  # type: ignore[union-attr]
            tokens_used=tokens_used,
        )

    # --- batch generation -----------------------------------------------------

    def generate_meanings_batch(self, system_prompt: str, user_prompt: str) -> list[BatchMeaningResult]:
        try:
            return asyncio.run(self._async_generate_batch(system_prompt, user_prompt))
        except AIServiceError:
            raise
        except CLINotFoundError as e:
            raise AIServiceError("Claude Code CLI not found. Install it at https://claude.ai/download") from e
        except CLIConnectionError as e:
            raise AIServiceError("Cannot connect to Claude. Run 'claude' to log in.") from e
        except ProcessError as e:
            raise AIServiceError(f"Claude process failed (exit {e.exit_code}). Run 'claude' to check auth.") from e
        except Exception as e:
            raise AIServiceError(str(e)) from e

    async def _async_generate_batch(self, system_prompt: str, user_prompt: str) -> list[BatchMeaningResult]:
        stderr_lines: list[str] = []

        options = ClaudeAgentOptions(
            model=self._model,
            system_prompt=system_prompt,
            max_turns=1,
            output_format=_BATCH_SCHEMA,
            stderr=stderr_lines.append,
        )
        structured: dict[str, Any] | None = None
        try:
            async for message in query(prompt=user_prompt, options=options):
                if isinstance(message, ResultMessage):
                    structured = message.structured_output
        except Exception as e:
            stderr_detail = " | ".join(stderr_lines).strip()
            detail = stderr_detail or str(e)
            if "authentication" in detail.lower() or "login" in detail.lower() or "not logged" in detail.lower():
                raise AIServiceError(f"Not authenticated. Run 'claude' to log in. ({detail})") from e
            raise AIServiceError(detail) from e

        if structured is None:
            raise AIServiceError("No structured output received from Claude")

        if isinstance(structured, str):
            structured = json.loads(structured)  # type: ignore[assignment]

        results: list[dict[str, Any]] = structured["results"]  # type: ignore[index]
        return [
            BatchMeaningResult(
                lemma=item["lemma"],
                pos=item["pos"],
                meaning=item["meaning"],
                ipa=item.get("ipa"),
            )
            for item in results
        ]
