from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import AnkiStatusDTO

if TYPE_CHECKING:
    from backend.domain.ports.anki_connector import AnkiConnector


class GetAnkiStatusUseCase:
    """Checks whether AnkiConnect is reachable."""

    def __init__(self, connector: AnkiConnector) -> None:
        self._connector = connector

    def execute(self) -> AnkiStatusDTO:
        available = self._connector.is_available()
        return AnkiStatusDTO(available=available)
