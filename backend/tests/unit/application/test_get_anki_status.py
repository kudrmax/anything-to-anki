from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_anki_status import GetAnkiStatusUseCase


@pytest.mark.unit
class TestGetAnkiStatusUseCase:
    def test_available(self) -> None:
        connector = MagicMock()
        connector.is_available.return_value = True
        result = GetAnkiStatusUseCase(connector).execute()
        assert result.available is True

    def test_not_available(self) -> None:
        connector = MagicMock()
        connector.is_available.return_value = False
        result = GetAnkiStatusUseCase(connector).execute()
        assert result.available is False
