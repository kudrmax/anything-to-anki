"""AI Proxy — runs on the host, serves meaning generation to the Docker container.

Usage:
    python ai_proxy.py                  # default port 8766
    python ai_proxy.py --port 9000      # custom port

Requires: pip install claude-agent-sdk fastapi uvicorn
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from typing import Any

import uvicorn

# Import directly — this script runs on the host where claude-agent-sdk is installed.
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query
from claude_agent_sdk.types import TextBlock
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("ai_proxy")

# Use the system-installed claude CLI (has Keychain auth) instead of the bundled one.
# shutil.which may fail in background processes with restricted PATH.
_SYSTEM_CLAUDE: str | None = shutil.which("claude") or "/opt/homebrew/bin/claude"

app = FastAPI(title="AI Proxy", version="0.3.0")
logger.info("Using claude CLI: %s", _SYSTEM_CLAUDE)
logger.info("Proxy env: http_proxy=%s https_proxy=%s",
            __import__("os").environ.get("http_proxy"),
            __import__("os").environ.get("https_proxy"))

_SINGLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "meaning": {"type": "string"},
        "translation": {"type": "string"},
        "synonyms": {"type": "string"},
        "ipa": {"type": "string"},
    },
    "required": ["meaning", "translation", "synonyms", "ipa"],
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
                    "ipa": {"type": "string"},
                },
                "required": [
                    "word_index", "meaning", "translation", "synonyms", "ipa",
                ],
            },
        }
    },
    "required": ["results"],
}


async def _generate_structured(
    system_prompt: str,
    user_prompt: str,
    model: str,
    schema: dict[str, Any],
) -> tuple[Any, int]:
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
    tokens_used = 0
    result_subtype: str | None = None
    error_context: list[str] = []

    async for message in query(prompt=user_prompt, options=options):
        if isinstance(message, AssistantMessage):
            if message.error:
                error_context.append(f"AssistantMessage.error={message.error}")
                logger.error("AI error: %s", message.error)
            for block in message.content:
                if isinstance(block, TextBlock):
                    error_context.append(f"AI text: {block.text[:500]}")

        elif isinstance(message, ResultMessage):
            result_subtype = message.subtype
            structured_output = message.structured_output
            usage = message.usage or {}
            tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

            if message.is_error or message.errors:
                logger.error(
                    "ResultMessage error: subtype=%s, is_error=%s, result=%s, errors=%s",
                    message.subtype, message.is_error, message.result, message.errors,
                )
                error_context.append(
                    f"result_error: subtype={message.subtype}, errors={message.errors}"
                )
            elif message.subtype != "success":
                logger.warning("ResultMessage subtype=%s (not success)", message.subtype)

    if structured_output is None:
        detail = f"subtype={result_subtype}, context={error_context}"
        logger.error("No structured output received: %s", detail)
        raise RuntimeError(f"AI returned no structured output: {detail}")

    return structured_output, tokens_used


class GenerateRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    model: str


class GenerateResponse(BaseModel):
    meaning: str
    translation: str
    synonyms: str
    ipa: str | None = None
    tokens_used: int


class BatchItem(BaseModel):
    word_index: int
    meaning: str
    translation: str
    synonyms: str
    ipa: str | None = None


class BatchGenerateResponse(BaseModel):
    results: list[BatchItem]
    tokens_used: int


@app.post("/generate-meaning")
async def generate_meaning(req: GenerateRequest) -> GenerateResponse:
    try:
        data, tokens_used = await _generate_structured(
            req.system_prompt, req.user_prompt, req.model, _SINGLE_SCHEMA
        )
    except Exception as e:
        logger.exception("generate-meaning: AI call failed")
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}") from e
    if not isinstance(data, dict):
        logger.error("generate-meaning: unexpected response type %s: %r", type(data), data)
        raise HTTPException(status_code=502, detail="Unexpected AI response format")
    try:
        resp = GenerateResponse(
            meaning=data.get("meaning", ""),
            translation=data.get("translation", ""),
            synonyms=data.get("synonyms", ""),
            ipa=data.get("ipa") or None,
            tokens_used=tokens_used,
        )
    except ValidationError as e:
        logger.error("generate-meaning response schema mismatch: %s\nraw=%r", e, data)
        raise HTTPException(
            status_code=502,
            detail=f"AI response schema mismatch (ai_proxy<->backend drift): {e}",
        ) from e
    logger.info("generate-meaning OK, tokens=%d", tokens_used)
    return resp


@app.post("/generate-meanings-batch")
async def generate_meanings_batch(req: GenerateRequest) -> BatchGenerateResponse:
    try:
        data, tokens_used = await _generate_structured(
            req.system_prompt, req.user_prompt, req.model, _BATCH_SCHEMA
        )
    except Exception as e:
        logger.exception("generate-meanings-batch: AI call failed")
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}") from e
    if not isinstance(data, dict) or "results" not in data:
        logger.error("generate-meanings-batch: unexpected response: %r", data)
        raise HTTPException(status_code=502, detail="Unexpected AI response format")
    try:
        resp = BatchGenerateResponse(
            results=data["results"], tokens_used=tokens_used,
        )
    except ValidationError as e:
        logger.error("generate-meanings-batch response schema mismatch: %s\nraw=%r", e, data)
        raise HTTPException(
            status_code=502,
            detail=f"AI response schema mismatch (ai_proxy<->backend drift): {e}",
        ) from e
    logger.info(
        "generate-meanings-batch OK, results=%d, tokens=%d",
        len(resp.results), tokens_used,
    )
    return resp


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Proxy for anything-to-anki")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)
