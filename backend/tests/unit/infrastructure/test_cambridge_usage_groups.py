import pytest
from backend.infrastructure.adapters.cambridge.usage_groups import (
    DEFAULT_USAGE_GROUP_ORDER,
    USAGE_GROUP_MAP,
    resolve_usage_group,
)


@pytest.mark.unit
class TestUsageGroupMap:
    def test_informal_variants(self) -> None:
        for raw in ("informal", "very informal", "slang", "infml"):
            assert USAGE_GROUP_MAP[raw] == "informal"

    def test_formal_variants(self) -> None:
        for raw in ("formal", "fml"):
            assert USAGE_GROUP_MAP[raw] == "formal"

    def test_specialized_with_typo(self) -> None:
        assert USAGE_GROUP_MAP["specalized"] == "specialized"
        assert USAGE_GROUP_MAP["specialized"] == "specialized"
        assert USAGE_GROUP_MAP["specialist"] == "specialized"

    def test_connotation_group(self) -> None:
        for raw in ("disapproving", "approving", "humorous"):
            assert USAGE_GROUP_MAP[raw] == "connotation"

    def test_old_fashioned_group(self) -> None:
        for raw in ("old-fashioned", "old use", "dated"):
            assert USAGE_GROUP_MAP[raw] == "old-fashioned"

    def test_offensive_group(self) -> None:
        for raw in ("offensive", "very offensive", "extremely offensive"):
            assert USAGE_GROUP_MAP[raw] == "offensive"

    def test_other_group(self) -> None:
        for raw in ("literary", "trademark", "child's word", "figurative", "not standard"):
            assert USAGE_GROUP_MAP[raw] == "other"


@pytest.mark.unit
class TestResolveUsageGroup:
    def test_known_usage(self) -> None:
        assert resolve_usage_group("informal") == "informal"

    def test_unknown_usage_returns_none(self) -> None:
        assert resolve_usage_group("totally_unknown_label") is None

    def test_case_insensitive(self) -> None:
        assert resolve_usage_group("Informal") == "informal"
        assert resolve_usage_group("FORMAL") == "formal"


@pytest.mark.unit
class TestDefaultOrder:
    def test_has_all_groups(self) -> None:
        expected = {"neutral", "informal", "formal", "specialized",
                    "connotation", "old-fashioned", "offensive", "other"}
        assert set(DEFAULT_USAGE_GROUP_ORDER) == expected

    def test_no_duplicates(self) -> None:
        assert len(DEFAULT_USAGE_GROUP_ORDER) == len(set(DEFAULT_USAGE_GROUP_ORDER))
