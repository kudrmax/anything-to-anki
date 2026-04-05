from __future__ import annotations

_MODEL_MAP: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
}


def model_id_for(key: str) -> str:
    """Map a settings key like 'sonnet' to the full model ID."""
    return _MODEL_MAP.get(key, "claude-sonnet-4-6")
