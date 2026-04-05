from __future__ import annotations

import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query
from claude_agent_sdk import CLIConnectionError, CLINotFoundError, ProcessError

from backend.domain.exceptions import AIServiceError
from backend.domain.ports.ai_service import AIService
from backend.domain.value_objects.generation_result import GenerationResult


class ClaudeAIService(AIService):
    """AIService implementation backed by Claude via claude-agent-sdk (CLI auth).

    generate_meaning() is synchronous and must be called from a thread
    (e.g. via asyncio.to_thread) so that asyncio.run() can create a fresh
    event loop without conflicting with the FastAPI event loop.
    """

    def __init__(self, model: str) -> None:
        self._model = model

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
            stderr=stderr_lines.append,
        )
        parts: list[str] = []
        tokens_used = 0
        try:
            async for message in query(prompt=user_prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    usage = message.usage or {}
                    tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        except Exception as e:
            stderr_detail = " | ".join(stderr_lines).strip()
            detail = stderr_detail or str(e)
            if "authentication" in detail.lower() or "login" in detail.lower() or "not logged" in detail.lower():
                raise AIServiceError(f"Not authenticated. Run 'claude' to log in. ({detail})") from e
            raise AIServiceError(detail) from e
        return GenerationResult(meaning=" ".join(parts).strip(), tokens_used=tokens_used)
