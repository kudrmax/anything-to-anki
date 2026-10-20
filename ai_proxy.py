"""AI Proxy — separate process that serves AI generation to the backend.

Usage:
    python ai_proxy.py                  # default port 8766
    python ai_proxy.py --port 9000      # custom port

Requires: pip install claude-agent-sdk fastapi uvicorn
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import uvicorn

# Import directly — claude-agent-sdk is installed for this process only ([ai-proxy] extra).
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query
from claude_agent_sdk.types import TextBlock
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from collections.abc import MutableMapping

# Make backend importable when ai_proxy is launched directly from the repo root.
_BACKEND_SRC = Path(__file__).parent / "backend" / "src"
if _BACKEND_SRC.exists() and str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from backend.infrastructure.logging_setup import configure_logging  # noqa: E402

configure_logging("ai_proxy")
logger = logging.getLogger("ai_proxy")

# Use the system-installed claude CLI (has Keychain auth) instead of the bundled one.
# shutil.which may fail in background processes with restricted PATH.
_SYSTEM_CLAUDE: str | None = shutil.which("claude") or "/opt/homebrew/bin/claude"

app = FastAPI(title="AI Proxy", version="0.3.0")
logger.info("Using claude CLI: %s", _SYSTEM_CLAUDE)
logger.info("Proxy env: http_proxy=%s https_proxy=%s",
            os.environ.get("http_proxy"), os.environ.get("https_proxy"))

_SINGLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "meaning": {"type": "string"},
        "translation": {"type": "string"},
        "synonyms": {"type": "string"},
        "examples": {"type": "string"},
        "ipa": {"type": "string"},
    },
    "required": ["meaning", "translation", "synonyms", "examples", "ipa"],
}

_BATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word_index": {"type": "integer"},
                    "meaning": {"type": "string"},
                    "translation": {"type": "string"},
                    "synonyms": {"type": "string"},
                    "examples": {"type": "string"},
                    "ipa": {"type": "string"},
                },
                "required": [
                    "word_index", "meaning", "translation", "synonyms", "examples", "ipa",
                ],
            },
        }
    },
    "required": ["results"],
}

_TOPIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "targets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "phrase": {"type": "string"},
                    "example": {"type": "string"},
                },
                "required": ["phrase", "example"],
            },
        }
    },
    "required": ["targets"],
}

_POLISH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "phrase_index": {"type": "integer"},
                    "phrase": {"type": "string"},
                },
                "required": ["phrase_index", "phrase"],
            },
        }
    },
    "required": ["results"],
}


BLOCKED_COUNTRIES: frozenset[str] = frozenset({"RU"})
_COUNTRY_CHECK_TIMEOUT = 5


async def _get_country() -> str | None:
    """Return ISO country code for the host's public IP, or None on failure."""
    try:
        async with httpx.AsyncClient(timeout=_COUNTRY_CHECK_TIMEOUT) as client:
            resp = await client.get("https://ipinfo.io/json")
            resp.raise_for_status()
            return resp.json().get("country")  # type: ignore[no-any-return]
    except Exception:
        logger.warning("Country check failed (network error)")
        return None


# The CLI's own errors that no retry of the same request fixes until the user acts.
SERVICE_ERRORS: frozenset[str] = frozenset(
    {"authentication_failed", "billing_error", "rate_limit"},
)


class AIUnavailableError(RuntimeError):
    """The AI can answer no request now: no login, a blocked country, a spent limit."""


def _ensure_country_allowed(country: str | None) -> None:
    if country is not None and country in BLOCKED_COUNTRIES:
        logger.error("Blocked country detected: %s. Turn on VPN.", country)
        raise AIUnavailableError(f"Blocked country: {country}. Turn on VPN.")


class UsageInfo(BaseModel):
    """Tokens one call consumed. input_tokens excludes the cached part of the prompt."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    model: str | None = None

    @property
    def total(self) -> int:
        return (
            self.input_tokens + self.output_tokens
            + self.cache_read_tokens + self.cache_creation_tokens
        )

    @classmethod
    def from_sdk(
        cls, usage: dict[str, Any], model_usage: dict[str, Any] | None = None,
    ) -> UsageInfo:
        return cls(
            input_tokens=usage.get("input_tokens") or 0,
            output_tokens=usage.get("output_tokens") or 0,
            cache_read_tokens=usage.get("cache_read_input_tokens") or 0,
            cache_creation_tokens=usage.get("cache_creation_input_tokens") or 0,
            model=_answering_model(model_usage or {}),
        )


def _answering_model(model_usage: dict[str, Any]) -> str | None:
    """The full model ID an alias like 'sonnet' resolved to: the one that wrote the most."""
    if not model_usage:
        return None
    return max(model_usage, key=lambda m: model_usage[m].get("outputTokens") or 0)


async def _generate_structured(
    system_prompt: str,
    user_prompt: str,
    model: str,
    schema: dict[str, Any],
) -> tuple[Any, UsageInfo]:
    country = await _get_country()
    _ensure_country_allowed(country)

    # Note: max_turns is NOT set — structured output requires multiple internal turns
    # (tool invocation turn + final result turn). Setting max_turns=1 causes error_max_turns.
    def _on_stderr(line: str) -> None:
        logger.error("claude-cli stderr: %s", line)

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=system_prompt,
        output_format={"type": "json_schema", "schema": schema},
        stderr=_on_stderr,
        cli_path=_SYSTEM_CLAUDE,
    )
    structured_output: Any = None
    usage = UsageInfo()
    result_subtype: str | None = None
    error_context: list[str] = []
    # What the CLI itself reported (e.g. an expired login). The SDK then raises
    # its own generic "returned an error result" exception, which hides it.
    cli_error: str | None = None
    service_error = False

    try:
        async for message in query(prompt=user_prompt, options=options):
            if isinstance(message, AssistantMessage):
                if message.error:
                    service_error = service_error or message.error in SERVICE_ERRORS
                    error_context.append(f"AssistantMessage.error={message.error}")
                    logger.error("AI error: %s", message.error)
                for block in message.content:
                    if isinstance(block, TextBlock):
                        error_context.append(f"AI text: {block.text[:500]}")

            elif isinstance(message, ResultMessage):
                result_subtype = message.subtype
                structured_output = message.structured_output
                usage = UsageInfo.from_sdk(message.usage or {}, message.model_usage)

                if message.is_error or message.errors:
                    logger.error(
                        "ResultMessage error: subtype=%s, is_error=%s, result=%s, errors=%s",
                        message.subtype, message.is_error, message.result, message.errors,
                    )
                    error_context.append(
                        f"result_error: subtype={message.subtype}, errors={message.errors}"
                    )
                    cli_error = message.result or cli_error
                elif message.subtype != "success":
                    logger.warning("ResultMessage subtype=%s (not success)", message.subtype)
    except Exception as e:
        if service_error:
            raise AIUnavailableError(cli_error or str(e)) from e
        if cli_error:
            raise RuntimeError(cli_error) from e
        raise

    if structured_output is None:
        detail = f"subtype={result_subtype}, context={error_context}"
        logger.error("No structured output received: %s", detail)
        raise RuntimeError(f"AI returned no structured output: {detail}")

    return structured_output, usage


class GenerateRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    model: str


async def _call_ai(
    endpoint: str, req: GenerateRequest, schema: dict[str, Any],
) -> tuple[Any, UsageInfo]:
    """Run one AI call: 503 when the AI is unavailable as a whole, 502 when this call failed."""
    try:
        return await _generate_structured(req.system_prompt, req.user_prompt, req.model, schema)
    except AIUnavailableError as e:
        logger.error("%s: AI unavailable: %s", endpoint, e)
        # The detail is the reason itself, ready to show to the user.
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logger.exception("%s: AI call failed", endpoint)
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}") from e


class GenerateResponse(BaseModel):
    meaning: str
    translation: str
    synonyms: str
    examples: str
    ipa: str | None = None
    usage: UsageInfo


class BatchItem(BaseModel):
    word_index: int
    meaning: str
    translation: str
    synonyms: str
    examples: str
    ipa: str | None = None


class BatchGenerateResponse(BaseModel):
    results: list[BatchItem]
    usage: UsageInfo


@app.post("/generate-meaning")
async def generate_meaning(req: GenerateRequest) -> GenerateResponse:
    data, usage = await _call_ai("generate-meaning", req, _SINGLE_SCHEMA)
    if not isinstance(data, dict):
        logger.error("generate-meaning: unexpected response type %s: %r", type(data), data)
        raise HTTPException(status_code=502, detail="Unexpected AI response format")
    try:
        resp = GenerateResponse(
            meaning=data.get("meaning", ""),
            translation=data.get("translation", ""),
            synonyms=data.get("synonyms", ""),
            examples=data.get("examples", ""),
            ipa=data.get("ipa") or None,
            usage=usage,
        )
    except ValidationError as e:
        logger.error("generate-meaning response schema mismatch: %s\nraw=%r", e, data)
        raise HTTPException(
            status_code=502,
            detail=f"AI response schema mismatch (ai_proxy<->backend drift): {e}",
        ) from e
    logger.info("generate-meaning OK, tokens=%d", usage.total)
    return resp


@app.post("/generate-meanings-batch")
async def generate_meanings_batch(req: GenerateRequest) -> BatchGenerateResponse:
    data, usage = await _call_ai("generate-meanings-batch", req, _BATCH_SCHEMA)
    if not isinstance(data, dict) or "results" not in data:
        logger.error("generate-meanings-batch: unexpected response: %r", data)
        raise HTTPException(status_code=502, detail="Unexpected AI response format")
    try:
        resp = BatchGenerateResponse(
            results=data["results"], usage=usage,
        )
    except ValidationError as e:
        logger.error("generate-meanings-batch response schema mismatch: %s\nraw=%r", e, data)
        raise HTTPException(
            status_code=502,
            detail=f"AI response schema mismatch (ai_proxy<->backend drift): {e}",
        ) from e
    logger.info(
        "generate-meanings-batch OK, results=%d, tokens=%d",
        len(resp.results), usage.total,
    )
    return resp


class TopicTargetItem(BaseModel):
    phrase: str
    example: str


class TopicTargetsResponse(BaseModel):
    targets: list[TopicTargetItem]
    usage: UsageInfo


@app.post("/generate-topic-targets")
async def generate_topic_targets(req: GenerateRequest) -> TopicTargetsResponse:
    data, usage = await _call_ai("generate-topic-targets", req, _TOPIC_SCHEMA)
    if not isinstance(data, dict) or "targets" not in data:
        logger.error("generate-topic-targets: unexpected response: %r", data)
        raise HTTPException(status_code=502, detail="Unexpected AI response format")
    try:
        resp = TopicTargetsResponse(targets=data["targets"], usage=usage)
    except ValidationError as e:
        logger.error("generate-topic-targets response schema mismatch: %s\nraw=%r", e, data)
        raise HTTPException(
            status_code=502,
            detail=f"AI response schema mismatch (ai_proxy<->backend drift): {e}",
        ) from e
    logger.info(
        "generate-topic-targets OK, targets=%d, tokens=%d",
        len(resp.targets), usage.total,
    )
    return resp


class PolishedPhraseItem(BaseModel):
    phrase_index: int
    phrase: str


class PolishPhrasesResponse(BaseModel):
    results: list[PolishedPhraseItem]
    usage: UsageInfo


@app.post("/polish-phrases-batch")
async def polish_phrases_batch(req: GenerateRequest) -> PolishPhrasesResponse:
    data, usage = await _call_ai("polish-phrases-batch", req, _POLISH_SCHEMA)
    if not isinstance(data, dict) or "results" not in data:
        logger.error("polish-phrases-batch: unexpected response: %r", data)
        raise HTTPException(status_code=502, detail="Unexpected AI response format")
    try:
        resp = PolishPhrasesResponse(results=data["results"], usage=usage)
    except ValidationError as e:
        logger.error("polish-phrases-batch response schema mismatch: %s\nraw=%r", e, data)
        raise HTTPException(
            status_code=502,
            detail=f"AI response schema mismatch (ai_proxy<->backend drift): {e}",
        ) from e
    logger.info(
        "polish-phrases-batch OK, results=%d, tokens=%d",
        len(resp.results), usage.total,
    )
    return resp


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# A process started from a Claude Code session inherits that session's variables. They
# point the CLI at the session's own login, and the CLI answers "Not logged in".
_INHERITED_ENV_PREFIXES = ("CLAUDE", "ANTHROPIC_")
_AUTH_STATUS_TIMEOUT = 30


def drop_inherited_claude_env(environ: MutableMapping[str, str]) -> list[str]:
    """Remove the Claude/Anthropic variables the proxy was started with. Returns their names."""
    dropped = sorted(k for k in environ if k.startswith(_INHERITED_ENV_PREFIXES))
    for name in dropped:
        del environ[name]
    return dropped


def cli_logged_in() -> bool:
    """Whether the claude CLI, run with the proxy's environment, has a login."""
    assert _SYSTEM_CLAUDE is not None
    status = subprocess.run(
        [_SYSTEM_CLAUDE, "auth", "status"],
        capture_output=True, text=True, timeout=_AUTH_STATUS_TIMEOUT, check=False,
    )
    try:
        return json.loads(status.stdout).get("loggedIn") is True
    except json.JSONDecodeError:
        logger.error("claude auth status: %s %s", status.stdout, status.stderr)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Proxy for anything-to-anki")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    dropped_env = drop_inherited_claude_env(os.environ)
    if dropped_env:
        logger.info("Dropped inherited env: %s", ", ".join(dropped_env))
    if not cli_logged_in():
        logger.error("claude CLI is not logged in: run `claude` and /login in a terminal")
        sys.exit(1)
    uvicorn.run(app, host="0.0.0.0", port=args.port)
