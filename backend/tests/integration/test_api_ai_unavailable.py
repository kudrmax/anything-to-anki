"""An AI route answers 503 when the AI is not available from here, 502 when a request to it
failed otherwise."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.domain.exceptions import AIServiceError, AIUnavailableError
from backend.domain.value_objects.ai_unavailable import AI_UNAVAILABLE_MARKER
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_container, get_db_session
from fastapi.testclient import TestClient

from tests.review_support import REVIEW_PARAMS, RunningMutation

if TYPE_CHECKING:
    from collections.abc import Generator

    from httpx import Response

pytestmark = pytest.mark.integration

PHRASE_ID = 1


class _FailingMeaning:
    def __init__(self, error: AIServiceError) -> None:
        self._error = error

    def execute(self, phrase_id: int) -> None:
        raise self._error


class _Container:
    """Builds only the meaning generation, which fails as the test says."""

    def __init__(self, error: AIServiceError) -> None:
        self._error = error

    def generate_meaning_use_case(self, session: object) -> _FailingMeaning:
        del session
        return _FailingMeaning(self._error)

    def review_mutation(self, session: object) -> RunningMutation:
        del session
        return RunningMutation()


def _answer(error: AIServiceError) -> Response:
    def no_session() -> Generator[MagicMock, None, None]:
        yield MagicMock()

    app.dependency_overrides[get_container] = lambda: _Container(error)
    app.dependency_overrides[get_db_session] = no_session
    try:
        client = TestClient(app)
        return client.post(f"/phrases/{PHRASE_ID}/generate-meaning", params=REVIEW_PARAMS)
    finally:
        app.dependency_overrides.clear()


def test_the_ai_unavailable_from_here_is_503() -> None:
    """The body still says it in the words the front's `isVpnError` looks for."""
    answer = _answer(AIUnavailableError(f"AI proxy error: {AI_UNAVAILABLE_MARKER}: RU"))
    assert answer.status_code == 503
    assert AI_UNAVAILABLE_MARKER in answer.json()["detail"]
    assert AI_UNAVAILABLE_MARKER == "Blocked country"


def test_another_ai_failure_is_502() -> None:
    answer = _answer(AIServiceError("AI proxy error: boom"))
    assert answer.status_code == 502
    assert AI_UNAVAILABLE_MARKER not in answer.json()["detail"]
