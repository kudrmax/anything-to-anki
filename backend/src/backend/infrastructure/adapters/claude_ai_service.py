from __future__ import annotations

import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
from claude_agent_sdk import CLIConnectionError, CLINotFoundError, ProcessError

from backend.domain.exceptions import AIServiceError
from backend.domain.ports.ai_service import AIService

_SYSTEM_PROMPT = (
    "You are a concise English dictionary assistant. "
    "Always return only the definition text — no labels, no commentary."
)

_PROMPT_TEMPLATE = """\
Word: "{lemma}" (part of speech: {pos})
Context: "{context}"

Write a brief definition (1–2 sentences, max 30 words) for the specific meaning used in this context.
Return only the definition text."""


class ClaudeAIService(AIService):
    """AIService implementation backed by Claude via claude-agent-sdk (CLI auth).

    generate_meaning() is synchronous and must be called from a thread
    (e.g. via asyncio.to_thread) so that asyncio.run() can create a fresh
    event loop without conflicting with the FastAPI event loop.
    """

    def __init__(self, model: str) -> None:
        self._model = model

    def generate_meaning(self, lemma: str, pos: str, context: str) -> str:
        prompt = _PROMPT_TEMPLATE.format(lemma=lemma, pos=pos, context=context)
        try:
            return asyncio.run(self._async_generate(prompt))
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

    async def _async_generate(self, prompt: str) -> str:
        stderr_lines: list[str] = []

        options = ClaudeAgentOptions(
            model=self._model,
            system_prompt=_SYSTEM_PROMPT,
            max_turns=1,
            stderr=stderr_lines.append,
        )
        parts: list[str] = []
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
        except Exception as e:
            stderr_detail = " | ".join(stderr_lines).strip()
            detail = stderr_detail or str(e)
            if "authentication" in detail.lower() or "login" in detail.lower() or "not logged" in detail.lower():
                raise AIServiceError(f"Not authenticated. Run 'claude' to log in. ({detail})") from e
            raise AIServiceError(detail) from e
        return " ".join(parts).strip()
