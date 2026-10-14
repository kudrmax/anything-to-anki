from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import AnkiProgressDTO
from backend.domain.exceptions import AnkiNotAvailableError

if TYPE_CHECKING:
    from backend.application.utils.known_from_anki import RefreshKnownFromAnki
    from backend.domain.ports.anki_connector import AnkiConnector


class CheckAnkiProgressUseCase:
    """'Check progress in Anki': which exported words Anki says are learned, without export."""

    def __init__(
        self, anki_connector: AnkiConnector, known_from_anki: RefreshKnownFromAnki,
    ) -> None:
        self._connector = anki_connector
        self._known_from_anki = known_from_anki

    def execute(self) -> AnkiProgressDTO:
        if not self._connector.is_available():
            raise AnkiNotAvailableError()
        return AnkiProgressDTO(matured=self._known_from_anki.run())
