import pytest
from backend.domain.value_objects.usage_distribution import UsageDistribution


@pytest.mark.unit
class TestUsageDistribution:
    def test_create_from_dict(self) -> None:
        ud = UsageDistribution({"informal": 0.6, "neutral": 0.4})
        assert ud.groups == {"informal": 0.6, "neutral": 0.4}

    def test_none_distribution(self) -> None:
        ud = UsageDistribution(None)
        assert ud.groups is None

    def test_primary_group_picks_first_in_order(self) -> None:
        ud = UsageDistribution({"informal": 0.4, "formal": 0.6})
        order = ["formal", "informal", "neutral"]
        assert ud.primary_group(order) == "formal"

    def test_primary_group_skips_missing(self) -> None:
        ud = UsageDistribution({"informal": 1.0})
        order = ["neutral", "formal", "informal"]
        assert ud.primary_group(order) == "informal"

    def test_primary_group_none_distribution_returns_neutral(self) -> None:
        ud = UsageDistribution(None)
        order = ["formal", "neutral", "informal"]
        assert ud.primary_group(order) == "neutral"

    def test_primary_group_empty_distribution_returns_neutral(self) -> None:
        ud = UsageDistribution({})
        order = ["formal", "neutral"]
        assert ud.primary_group(order) == "neutral"

    def test_primary_group_no_match_returns_neutral(self) -> None:
        ud = UsageDistribution({"unknown_group": 1.0})
        order = ["neutral", "informal"]
        assert ud.primary_group(order) == "neutral"

    def test_rank_returns_index(self) -> None:
        ud = UsageDistribution({"informal": 1.0})
        order = ["neutral", "informal", "formal"]
        assert ud.rank(order) == 1

    def test_rank_none_distribution_returns_neutral_index(self) -> None:
        ud = UsageDistribution(None)
        order = ["formal", "neutral", "informal"]
        assert ud.rank(order) == 1

    def test_to_dict_and_back(self) -> None:
        original = {"informal": 0.6, "neutral": 0.4}
        ud = UsageDistribution(original)
        assert ud.to_dict() == original

    def test_to_dict_none(self) -> None:
        ud = UsageDistribution(None)
        assert ud.to_dict() is None
