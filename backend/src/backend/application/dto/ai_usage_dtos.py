from __future__ import annotations

from datetime import datetime  # noqa: TC003 — pydantic resolves field types at runtime
from enum import StrEnum

from pydantic import BaseModel

from backend.domain.value_objects.ai_feature import AIFeature  # noqa: TC001 — pydantic field type


class UsagePeriod(StrEnum):
    TODAY = "today"
    WEEK = "7d"
    MONTH = "30d"
    ALL = "all"


class UsageBucketSize(StrEnum):
    HOUR = "hour"
    DAY = "day"


class TokenCountsDTO(BaseModel):
    """Token counters as the AI reports them; total is their sum."""

    total: int
    sent_uncached: int
    cache_write: int
    cache_read: int
    answer: int


class AIUsageTotalsDTO(BaseModel):
    tokens: TokenCountsDTO
    requests: int
    failed_requests: int
    # Change of total tokens against the same-length period right before;
    # None when there is nothing to compare with.
    change_percent: float | None
    # Average tokens spent per generated meaning; None when no meanings were generated.
    tokens_per_meaning: int | None


class FeatureTokensDTO(BaseModel):
    feature: AIFeature
    tokens: int


class AIUsageBucketDTO(BaseModel):
    """One bar of the chart: an hour or a day in the requested timezone."""

    start: datetime
    total_tokens: int
    # The features of AIUsageStatsDTO.features in the same order, zeros included.
    features: list[FeatureTokensDTO]


class AIUsageFeatureDTO(BaseModel):
    feature: AIFeature
    tokens: TokenCountsDTO
    requests: int
    failed_requests: int
    items: int
    share_percent: float


class AIUsageStatsDTO(BaseModel):
    period: UsagePeriod
    bucket_size: UsageBucketSize
    # When the first AI call was recorded; None while nothing has been recorded.
    tracking_since: datetime | None
    totals: AIUsageTotalsDTO
    buckets: list[AIUsageBucketDTO]
    # Most tokens first; features never used in the period are left out.
    features: list[AIUsageFeatureDTO]
