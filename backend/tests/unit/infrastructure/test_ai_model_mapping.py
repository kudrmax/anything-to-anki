from __future__ import annotations

import pytest
from backend.infrastructure.adapters.ai_model_mapping import model_id_for

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("key", ["haiku", "sonnet", "opus"])
def test_known_key_asks_for_latest_model_of_its_family(key: str) -> None:
    assert model_id_for(key) == key


def test_unknown_key_falls_back_to_sonnet() -> None:
    assert model_id_for("gpt") == "sonnet"
