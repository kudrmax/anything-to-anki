from __future__ import annotations

import pytest
from backend.domain.value_objects.source_scope import ScopeKind, SourceScope


@pytest.mark.unit
class TestSourceScope:
    def test_parse(self) -> None:
        assert SourceScope.parse("all") == SourceScope.all()
        assert SourceScope.parse("unsorted") == SourceScope.unsorted()
        assert SourceScope.parse("12") == SourceScope(ScopeKind.COLLECTION, 12)

    @pytest.mark.parametrize("raw", ["", "-1", "abc", "1.5"])
    def test_parse_rejects_garbage(self, raw: str) -> None:
        with pytest.raises(ValueError):
            SourceScope.parse(raw)
