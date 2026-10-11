from __future__ import annotations

# Claude CLI aliases: each resolves to the latest model of its family.
_MODEL_MAP: dict[str, str] = {
    "haiku": "haiku",
    "sonnet": "sonnet",
    "opus": "opus",
}
_DEFAULT_MODEL: str = "sonnet"


def model_id_for(key: str) -> str:
    """Map a settings key like 'sonnet' to the model the Claude CLI is asked for."""
    return _MODEL_MAP.get(key, _DEFAULT_MODEL)
