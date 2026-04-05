"""AI Proxy — runs on the host, serves meaning generation to the Docker container.

Usage:
    python ai_proxy.py                  # default port 8766
    python ai_proxy.py --port 9000      # custom port

Requires: pip install claude-agent-sdk fastapi uvicorn
"""
from __future__ import annotations

import argparse
import asyncio

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import directly — this script runs on the host where claude-agent-sdk is installed.
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

app = FastAPI(title="AI Proxy", version="0.2.0")


class GenerateRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    model: str


class GenerateResponse(BaseModel):
    meaning: str
    tokens_used: int


async def _generate(system_prompt: str, user_prompt: str, model: str) -> tuple[str, int]:
    options = ClaudeAgentOptions(
        model=model,
        system_prompt=system_prompt,
        max_turns=1,
    )
    parts: list[str] = []
    tokens_used = 0
    async for message in query(prompt=user_prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    parts.append(block.text)
        elif isinstance(message, ResultMessage):
            usage = message.usage or {}
            tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
    return " ".join(parts).strip(), tokens_used


@app.post("/generate-meaning")
async def generate_meaning(req: GenerateRequest) -> GenerateResponse:
    try:
        meaning, tokens_used = await _generate(req.system_prompt, req.user_prompt, req.model)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return GenerateResponse(meaning=meaning, tokens_used=tokens_used)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Proxy for anything-to-anki")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)
