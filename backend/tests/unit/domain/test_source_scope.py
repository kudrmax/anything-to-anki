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

    def test_parse_source(self) -> None:
        assert SourceScope.parse("source-7") == SourceScope.source(7)
        assert SourceScope.parse("7") == SourceScope.collection(7)

    @pytest.mark.parametrize(
        "raw",
        ["source-", "source-x", "source--1", "source-1.5", "source-7\n", "source-\u0663"],
    )
    def test_parse_rejects_bad_source(self, raw: str) -> None:
        with pytest.raises(ValueError):
            SourceScope.parse(raw)

    def test_only_unsorted_is_not_for_review(self) -> None:
        scopes = [
            SourceScope.all(),
            SourceScope.unsorted(),
            SourceScope.collection(1),
            SourceScope.source(1),
        ]
        assert [s.is_reviewable for s in scopes] == [True, False, True, True]
