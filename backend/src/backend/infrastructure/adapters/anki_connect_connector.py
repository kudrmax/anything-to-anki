from __future__ import annotations

import os

import httpx

from backend.domain.ports.anki_connector import AnkiConnector

_ANKI_URL = os.getenv("ANKI_URL", "http://localhost:8765")
_VERSION = 6

_DEFAULT_MODEL_NAME = "AnythingToAnkiType"
_DEFAULT_MODEL_FIELDS = ["Sentence", "Target", "Meaning", "IPA"]

_CARD_CSS = """.card { font-family: Arial, sans-serif; font-size: 18px; text-align: left; color: #222; background-color: #fff; padding: 20px; }"""

_FRONT_TEMPLATE = "{{Sentence}}"
_BACK_TEMPLATE = "{{FrontSide}}<hr id=answer>{{Target}}&nbsp;[{{IPA}}]<br><br>{{Meaning}}"


class AnkiConnectConnector(AnkiConnector):
    """Communicates with AnkiConnect via its HTTP JSON-RPC API."""

    def __init__(self, url: str = _ANKI_URL) -> None:
        self._url = url

    def _invoke(self, action: str, **params: object) -> object:
        payload = {"action": action, "version": _VERSION, "params": params}
        response = httpx.post(self._url, json=payload, timeout=5.0)
        response.raise_for_status()
        result = response.json()
        if result.get("error"):
            raise RuntimeError(f"AnkiConnect error: {result['error']}")
        return result.get("result")

    def get_version(self) -> int:
        return int(self._invoke("version"))  # type: ignore[arg-type]

    def is_available(self) -> bool:
        try:
            self._invoke("version")
            return True
        except (httpx.ConnectError, httpx.TimeoutException, Exception):  # noqa: BLE001
            return False

    def ensure_note_type(self, model_name: str, fields: list[str]) -> None:
        existing: list[str] = self._invoke("modelNames")  # type: ignore[assignment]
        if model_name in existing:
            return
        self._invoke(
            "createModel",
            modelName=model_name,
            inOrderFields=fields,
            css=_CARD_CSS,
            cardTemplates=[
                {
                    "Name": "AnythingToAnki Card",
                    "Front": _FRONT_TEMPLATE,
                    "Back": _BACK_TEMPLATE,
                }
            ],
        )

    def ensure_deck(self, deck_name: str) -> None:
        self._invoke("createDeck", deck=deck_name)

    def find_notes_by_target(self, deck_name: str, target: str) -> list[int]:
        query = f'note:{_DEFAULT_MODEL_NAME} Target:"{target}"'
        result = self._invoke("findNotes", query=query)
        return list(result) if result else []  # type: ignore[arg-type]

    def add_notes(
        self,
        deck_name: str,
        model_name: str,
        notes: list[dict[str, str]],
    ) -> list[int | None]:
        anki_notes = [
            {
                "deckName": deck_name,
                "modelName": model_name,
                "fields": note,
                "options": {"allowDuplicate": False},
                "tags": ["anything-to-anki"],
            }
            for note in notes
        ]
        result = self._invoke("addNotes", notes=anki_notes)
        return list(result) if result else []  # type: ignore[arg-type]

    def get_model_field_names(self, model_name: str) -> list[str] | None:
        try:
            existing: list[str] = self._invoke("modelNames")  # type: ignore[assignment]
            if model_name not in existing:
                return None
            fields = self._invoke("modelFieldNames", modelName=model_name)
            return list(fields)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            return None
