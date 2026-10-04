from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.application.dto.ai_usage_dtos import (
    AIUsageBucketDTO,
    AIUsageFeatureDTO,
    AIUsageStatsDTO,
    AIUsageTotalsDTO,
    FeatureTokensDTO,
    TokenCountsDTO,
    UsageBucketSize,
    UsagePeriod,
)
from backend.domain.value_objects.ai_feature import AIFeature
from backend.domain.value_objects.token_usage import TokenUsage

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from backend.domain.entities.ai_usage_record import AIUsageRecord
    from backend.domain.ports.ai_usage_repository import AIUsageRepository

PERIOD_DAYS: dict[UsagePeriod, int] = {
    UsagePeriod.TODAY: 1,
    UsagePeriod.WEEK: 7,
    UsagePeriod.MONTH: 30,
}
MEANING_FEATURES: frozenset[AIFeature] = frozenset({
    AIFeature.MEANING_BATCH,
    AIFeature.MEANING_SINGLE,
})
PERCENT = 100
PERCENT_DIGITS = 1


@dataclass
class _Tally:
    usage: TokenUsage = field(default_factory=TokenUsage)
    requests: int = 0
    failed_requests: int = 0
    items: int = 0

    def add(self, record: AIUsageRecord) -> None:
        self.usage += record.usage
        self.requests += 1
        self.items += record.item_count
        if not record.succeeded:
            self.failed_requests += 1


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


class GetAIUsageStatsUseCase:
    """Token usage of AI calls over a period: totals, per feature and per hour or day.

    Hours and days are those of the caller's timezone.
    """

    def __init__(
        self,
        usage_repo: AIUsageRepository,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._usage_repo = usage_repo
        self._now = now

    def execute(self, period: UsagePeriod, timezone: str) -> AIUsageStatsDTO:
        zone = _zone(timezone)
        now = self._now().astimezone(zone)
        tracking_since = self._usage_repo.first_recorded_at()
        start = _period_start(period, now, tracking_since)
        records = self._usage_repo.list_between(start, now) if start is not None else []
        bucket_size = UsageBucketSize.HOUR if period is UsagePeriod.TODAY else UsageBucketSize.DAY

        by_feature: dict[AIFeature, _Tally] = defaultdict(_Tally)
        total = _Tally()
        for record in records:
            by_feature[record.feature].add(record)
            total.add(record)
        features = sorted(
            by_feature,
            key=lambda f: (-by_feature[f].usage.total, list(AIFeature).index(f)),
        )

        return AIUsageStatsDTO(
            period=period,
            bucket_size=bucket_size,
            tracking_since=tracking_since,
            totals=AIUsageTotalsDTO(
                tokens=_token_counts(total.usage),
                requests=total.requests,
                failed_requests=total.failed_requests,
                change_percent=self._change_percent(period, start, now, total.usage.total),
                tokens_per_meaning=_tokens_per_meaning(by_feature),
            ),
            buckets=_buckets(records, features, start, now, bucket_size),
            features=[
                AIUsageFeatureDTO(
                    feature=feature,
                    tokens=_token_counts(by_feature[feature].usage),
                    requests=by_feature[feature].requests,
                    failed_requests=by_feature[feature].failed_requests,
                    items=by_feature[feature].items,
                    share_percent=_percent(by_feature[feature].usage.total, total.usage.total),
                )
                for feature in features
            ],
        )

    def _change_percent(
        self, period: UsagePeriod, start: datetime | None, now: datetime, tokens: int,
    ) -> float | None:
        if period is UsagePeriod.ALL or start is None:
            return None
        previous_start = start - (now - start)
        previous = sum(r.usage.total for r in self._usage_repo.list_between(previous_start, start))
        if previous == 0:
            return None
        return round((tokens - previous) / previous * PERCENT, PERCENT_DIGITS)


def _zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise ValueError(f"Unknown timezone: {timezone}") from e


def _midnight(day: date, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time(), tzinfo=zone)


def _period_start(
    period: UsagePeriod, now: datetime, tracking_since: datetime | None,
) -> datetime | None:
    zone = now.tzinfo
    assert isinstance(zone, ZoneInfo)
    if period is UsagePeriod.ALL:
        if tracking_since is None:
            return None
        return _midnight(tracking_since.astimezone(zone).date(), zone)
    first_day = now.date() - timedelta(days=PERIOD_DAYS[period] - 1)
    return _midnight(first_day, zone)


def _bucket_starts(
    start: datetime, now: datetime, bucket_size: UsageBucketSize,
) -> list[datetime]:
    zone = now.tzinfo
    assert isinstance(zone, ZoneInfo)
    if bucket_size is UsageBucketSize.HOUR:
        return [start.replace(hour=hour) for hour in range(now.hour + 1)]
    days = (now.date() - start.date()).days
    return [_midnight(start.date() + timedelta(days=offset), zone) for offset in range(days + 1)]


def _bucket_of(moment: datetime, zone: ZoneInfo, bucket_size: UsageBucketSize) -> datetime:
    local = moment.astimezone(zone)
    if bucket_size is UsageBucketSize.HOUR:
        return local.replace(minute=0, second=0, microsecond=0)
    return _midnight(local.date(), zone)


def _buckets(
    records: Iterable[AIUsageRecord],
    features: list[AIFeature],
    start: datetime | None,
    now: datetime,
    bucket_size: UsageBucketSize,
) -> list[AIUsageBucketDTO]:
    if start is None:
        return []
    zone = now.tzinfo
    assert isinstance(zone, ZoneInfo)
    tokens: dict[datetime, dict[AIFeature, int]] = defaultdict(lambda: defaultdict(int))
    for record in records:
        tokens[_bucket_of(record.created_at, zone, bucket_size)][record.feature] += (
            record.usage.total
        )
    return [
        AIUsageBucketDTO(
            start=bucket,
            total_tokens=sum(tokens[bucket].values()),
            features=[
                FeatureTokensDTO(feature=feature, tokens=tokens[bucket][feature])
                for feature in features
            ],
        )
        for bucket in _bucket_starts(start, now, bucket_size)
    ]


def _token_counts(usage: TokenUsage) -> TokenCountsDTO:
    return TokenCountsDTO(
        total=usage.total,
        sent=usage.sent,
        sent_uncached=usage.input_tokens,
        cache_write=usage.cache_creation_tokens,
        cache_read=usage.cache_read_tokens,
        answer=usage.output_tokens,
    )


def _tokens_per_meaning(by_feature: dict[AIFeature, _Tally]) -> int | None:
    meanings = [by_feature[f] for f in MEANING_FEATURES if f in by_feature]
    items = sum(t.items for t in meanings)
    if items == 0:
        return None
    return round(sum(t.usage.total for t in meanings) / items)


def _percent(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round(part / whole * PERCENT, PERCENT_DIGITS)
