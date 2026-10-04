from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.value_objects.ai_feature import AIFeature
    from backend.domain.value_objects.token_usage import TokenUsage


@dataclass(frozen=True)
class AIUsageRecord:
    """One AI call: what it was for and what it cost in tokens.

    A failed call is kept too, with no tokens, so failures can be counted.
    """

    feature: AIFeature
    model: str
    usage: TokenUsage
    # How many results the call returned: meanings, phrases or targets.
    item_count: int
    duration_ms: int
    succeeded: bool
    created_at: datetime
    id: int | None = None
