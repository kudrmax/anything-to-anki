"""Cambridge usage label → usage group mapping and helpers."""
from __future__ import annotations

USAGE_GROUP_MAP: dict[str, str] = {
    # informal
    "informal": "informal",
    "very informal": "informal",
    "slang": "informal",
    "infml": "informal",
    # formal
    "formal": "formal",
    "fml": "formal",
    # specialized
    "specialized": "specialized",
    "specialist": "specialized",
    "specalized": "specialized",
    # connotation
    "disapproving": "connotation",
    "approving": "connotation",
    "humorous": "connotation",
    # old-fashioned
    "old-fashioned": "old-fashioned",
    "old use": "old-fashioned",
    "dated": "old-fashioned",
    # offensive
    "offensive": "offensive",
    "very offensive": "offensive",
    "extremely offensive": "offensive",
    # other
    "literary": "other",
    "trademark": "other",
    "child's word": "other",
    "figurative": "other",
    "not standard": "other",
}

DEFAULT_USAGE_GROUP_ORDER: list[str] = [
    "neutral",
    "informal",
    "formal",
    "specialized",
    "connotation",
    "old-fashioned",
    "offensive",
    "other",
]


def resolve_usage_group(raw_usage: str) -> str | None:
    """Map a raw Cambridge usage label to a usage group name.

    Returns None if the label is not recognized.
    """
    return USAGE_GROUP_MAP.get(raw_usage.lower().strip())
