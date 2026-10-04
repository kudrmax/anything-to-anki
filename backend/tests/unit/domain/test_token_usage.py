from __future__ import annotations

import pytest
from backend.domain.value_objects.token_usage import TokenUsage


@pytest.mark.unit
class TestTokenUsage:
    def test_total_includes_cached_tokens(self) -> None:
        usage = TokenUsage(
            input_tokens=1, output_tokens=20, cache_read_tokens=300, cache_creation_tokens=4000,
        )
        assert usage.total == 4321

    def test_empty_usage_is_zero(self) -> None:
        assert TokenUsage().total == 0

    def test_sum_adds_each_kind(self) -> None:
        assert TokenUsage(1, 2, 3, 4) + TokenUsage(10, 20, 30, 40) == TokenUsage(11, 22, 33, 44)
