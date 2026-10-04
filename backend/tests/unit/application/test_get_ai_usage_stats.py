from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.application.dto.ai_usage_dtos import AIUsageStatsDTO, UsageBucketSize, UsagePeriod
from backend.application.use_cases.get_ai_usage_stats import GetAIUsageStatsUseCase
from backend.domain.entities.ai_usage_record import AIUsageRecord
from backend.domain.ports.ai_usage_repository import AIUsageRepository
from backend.domain.value_objects.ai_feature import AIFeature
from backend.domain.value_objects.token_usage import TokenUsage

MOSCOW = "Europe/Moscow"
# 2026-10-04 15:30 in Moscow (UTC+3).
NOW = datetime(2026, 10, 4, 12, 30, tzinfo=UTC)


class InMemoryAIUsageRepository(AIUsageRepository):
    def __init__(self, records: list[AIUsageRecord]) -> None:
        self._records = sorted(records, key=lambda r: r.created_at)

    def add(self, record: AIUsageRecord) -> AIUsageRecord:
        self._records.append(record)
        return record

    def list_between(self, start: datetime | None, end: datetime) -> list[AIUsageRecord]:
        return [
            r for r in self._records
            if (start is None or r.created_at >= start) and r.created_at < end
        ]

    def first_recorded_at(self) -> datetime | None:
        return self._records[0].created_at if self._records else None


def _record(
    at: datetime,
    feature: AIFeature = AIFeature.MEANING_BATCH,
    tokens: int = 100,
    items: int = 1,
    succeeded: bool = True,
) -> AIUsageRecord:
    return AIUsageRecord(
        feature=feature,
        model="m",
        usage=TokenUsage(input_tokens=tokens),
        item_count=items,
        duration_ms=1000,
        succeeded=succeeded,
        created_at=at,
    )


def _stats(
    records: list[AIUsageRecord], period: UsagePeriod, tz: str = MOSCOW,
) -> AIUsageStatsDTO:
    use_case = GetAIUsageStatsUseCase(InMemoryAIUsageRepository(records), now=lambda: NOW)
    return use_case.execute(period, tz)


@pytest.mark.unit
class TestGetAIUsageStats:
    def test_nothing_recorded_yet(self) -> None:
        stats = _stats([], UsagePeriod.ALL)

        assert stats.tracking_since is None
        assert stats.totals.tokens.total == 0
        assert stats.totals.change_percent is None
        assert stats.totals.tokens_per_meaning is None
        assert stats.buckets == []
        assert stats.features == []

    def test_week_has_a_bucket_for_every_day_including_empty_ones(self) -> None:
        stats = _stats([_record(datetime(2026, 10, 1, 9, tzinfo=UTC))], UsagePeriod.WEEK)

        assert stats.bucket_size is UsageBucketSize.DAY
        assert [b.start.day for b in stats.buckets] == [28, 29, 30, 1, 2, 3, 4]
        assert [b.total_tokens for b in stats.buckets] == [0, 0, 0, 100, 0, 0, 0]

    def test_days_follow_the_callers_timezone(self) -> None:
        # 22:30 UTC on Oct 2 is already Oct 3 in Moscow.
        stats = _stats([_record(datetime(2026, 10, 2, 22, 30, tzinfo=UTC))], UsagePeriod.WEEK)

        by_day = {b.start.day: b.total_tokens for b in stats.buckets}
        assert by_day[3] == 100
        assert by_day[2] == 0

    def test_today_is_split_by_hour_up_to_now(self) -> None:
        stats = _stats([_record(datetime(2026, 10, 4, 6, 10, tzinfo=UTC))], UsagePeriod.TODAY)

        assert stats.bucket_size is UsageBucketSize.HOUR
        assert len(stats.buckets) == 16  # 00:00 … 15:00 Moscow
        assert stats.buckets[9].total_tokens == 100

    def test_records_outside_the_period_are_ignored(self) -> None:
        records = [
            _record(datetime(2026, 9, 1, tzinfo=UTC), tokens=999),
            _record(datetime(2026, 10, 4, 8, tzinfo=UTC), tokens=50),
        ]
        stats = _stats(records, UsagePeriod.WEEK)

        assert stats.totals.tokens.total == 50

    def test_features_are_broken_down_and_sorted_by_tokens(self) -> None:
        at = datetime(2026, 10, 4, 8, tzinfo=UTC)
        records = [
            _record(at, AIFeature.PHRASE_POLISH, tokens=100),
            _record(at, AIFeature.MEANING_BATCH, tokens=250),
            _record(at, AIFeature.MEANING_BATCH, tokens=50, succeeded=False),
            _record(at, AIFeature.TOPIC_TARGETS, tokens=100),
        ]
        stats = _stats(records, UsagePeriod.WEEK)

        assert [f.feature for f in stats.features] == [
            AIFeature.MEANING_BATCH, AIFeature.PHRASE_POLISH, AIFeature.TOPIC_TARGETS,
        ]
        batch = stats.features[0]
        assert batch.tokens.total == 300
        assert batch.tokens.sent_uncached == 300
        assert batch.tokens.answer == 0
        assert batch.requests == 2
        assert batch.failed_requests == 1
        assert batch.share_percent == 60.0
        assert stats.totals.requests == 4
        assert stats.totals.failed_requests == 1
        today = stats.buckets[-1]
        assert [(f.feature, f.tokens) for f in today.features] == [
            (AIFeature.MEANING_BATCH, 300),
            (AIFeature.PHRASE_POLISH, 100),
            (AIFeature.TOPIC_TARGETS, 100),
        ]

    def test_tokens_per_meaning_counts_generated_meanings_only(self) -> None:
        at = datetime(2026, 10, 4, 8, tzinfo=UTC)
        records = [
            _record(at, AIFeature.MEANING_BATCH, tokens=900, items=3),
            _record(at, AIFeature.MEANING_SINGLE, tokens=300, items=1),
            _record(at, AIFeature.PHRASE_POLISH, tokens=5000, items=10),
        ]
        stats = _stats(records, UsagePeriod.WEEK)

        assert stats.totals.tokens_per_meaning == 300

    def test_change_against_the_same_length_period_before(self) -> None:
        records = [
            _record(datetime(2026, 9, 25, 9, tzinfo=UTC), tokens=200),
            _record(datetime(2026, 10, 3, 9, tzinfo=UTC), tokens=300),
        ]
        stats = _stats(records, UsagePeriod.WEEK)

        assert stats.totals.change_percent == 50.0

    def test_no_change_without_earlier_usage(self) -> None:
        stats = _stats([_record(datetime(2026, 10, 3, 9, tzinfo=UTC))], UsagePeriod.WEEK)

        assert stats.totals.change_percent is None

    def test_all_time_starts_on_the_day_of_the_first_record(self) -> None:
        stats = _stats([_record(datetime(2026, 10, 2, 9, tzinfo=UTC))], UsagePeriod.ALL)

        assert stats.tracking_since == datetime(2026, 10, 2, 9, tzinfo=UTC)
        assert [b.start.day for b in stats.buckets] == [2, 3, 4]
        assert stats.totals.change_percent is None

    def test_unknown_timezone_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown timezone"):
            _stats([], UsagePeriod.WEEK, tz="Mars/Olympus")
