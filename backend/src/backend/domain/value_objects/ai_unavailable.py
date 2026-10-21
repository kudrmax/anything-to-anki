"""The AI proxy's answer when the host is outside the country the AI is offered in."""
from __future__ import annotations

AI_UNAVAILABLE_MARKER = "Blocked country"


def is_ai_unavailable(error: str | None) -> bool:
    """The error says the AI is not available from here, not that a request failed."""
    return error is not None and AI_UNAVAILABLE_MARKER in error
