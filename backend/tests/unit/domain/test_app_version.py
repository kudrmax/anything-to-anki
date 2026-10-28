from __future__ import annotations

import pytest
from backend.domain.value_objects.app_version import AppVersion

pytestmark = pytest.mark.unit


def test_parse_orders_and_compares() -> None:
    assert AppVersion.parse("v1.10.0") > AppVersion.parse("1.9.9")
    assert str(AppVersion.parse("v1.2.3")) == "1.2.3"
    assert AppVersion.parse("1.2.3") == AppVersion(1, 2, 3)


@pytest.mark.parametrize("text", ["", "1.2", "1.2.3.4", "a.b.c", "v", "1.2.x", " 1.2.3"])
def test_parse_rejects_garbage(text: str) -> None:
    with pytest.raises(ValueError, match="version"):
        AppVersion.parse(text)
