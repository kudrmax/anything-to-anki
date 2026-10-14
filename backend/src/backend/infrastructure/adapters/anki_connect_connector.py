from __future__ import annotations

import logging
import os
from typing import cast

import httpx

from backend.domain.ports.anki_connector import AnkiConnector
from backend.domain.value_objects.note_maturity import NoteCards

logger = logging.getLogger(__name__)

_ANKI_URL = os.getenv("ANKI_URL", "http://localhost:8765")
_VERSION = 6
# Notes per `findCards` and cards per `cardsInfo`: keeps each request small.
ANKI_BATCH_SIZE = 500
_SUSPENDED_QUEUE = -1

_CARD_TEMPLATE_NAME = "AnythingToAnki Card"
_CLOZE_TEMPLATE_NAME = "AnythingToAnki Cloze"

_FALLBACK_FRONT = "{{Sentence}}"
_FALLBACK_BACK = "{{FrontSide}}<hr id=answer>{{Target}}<br>{{Meaning}}"
_FALLBACK_CLOZE_FRONT = "{{cloze:Text}}"
_FALLBACK_CLOZE_BACK = "{{cloze:Text}}<hr id=answer>{{Target}}"
_FALLBACK_CSS = (
    ".card { font-family: Arial, sans-serif; font-size: 18px; text-align: left;"
    " color: #222; background-color: #fff; padding: 20px; }"
)


def _quote(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _quote_value(text: str) -> str:
    """A field value matched literally: Anki reads `*` and `_` in it as wildcards."""
    return _quote(text).replace("*", "\\*").replace("_", "\\_")


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
        result = self._invoke("version")
        return cast("int", result)

    def is_available(self) -> bool:
        try:
            self._invoke("version")
            return True
        except (httpx.ConnectError, httpx.TimeoutException, Exception):  # noqa: BLE001
            logger.debug("AnkiConnect.is_available probe failed", exc_info=True)
            return False

    def ensure_note_type(
        self,
        model_name: str,
        fields: list[str],
        *,
        front_template: str | None = None,
        back_template: str | None = None,
        css: str | None = None,
        is_cloze: bool = False,
    ) -> None:
        existing = cast("list[str]", self._invoke("modelNames"))
        if model_name not in existing:
            name, front, back = (
                (_CLOZE_TEMPLATE_NAME, _FALLBACK_CLOZE_FRONT, _FALLBACK_CLOZE_BACK)
                if is_cloze
                else (_CARD_TEMPLATE_NAME, _FALLBACK_FRONT, _FALLBACK_BACK)
            )
            self._invoke(
                "createModel",
                modelName=model_name,
                inOrderFields=fields,
                css=css or _FALLBACK_CSS,
                isCloze=is_cloze,
                cardTemplates=[
                    {
                        "Name": name,
                        "Front": front_template or front,
                        "Back": back_template or back,
                    }
                ],
            )
            return

        current_fields = cast(
            "list[str]",
            self._invoke("modelFieldNames", modelName=model_name),
        )
        for idx, field in enumerate(fields):
            if field not in current_fields:
                self._invoke(
                    "modelFieldAdd",
                    modelName=model_name,
                    fieldName=field,
                    index=idx,
                )

    def ensure_deck(self, deck_name: str) -> None:
        self._invoke("createDeck", deck=deck_name)

    def find_notes_by_target(
        self, deck_name: str, model_name: str, target_field: str, target: str
    ) -> list[int]:
        query = f'note:"{_quote(model_name)}" "{_quote(target_field)}:{_quote_value(target)}"'
        raw = self._invoke("findNotes", query=query)
        return cast("list[int]", raw) if raw else []

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
        raw = self._invoke("addNotes", notes=anki_notes)
        return cast("list[int | None]", raw) if raw else []

    def get_model_field_names(self, model_name: str) -> list[str] | None:
        try:
            existing = cast("list[str]", self._invoke("modelNames"))
            if model_name not in existing:
                return None
            raw_fields = self._invoke("modelFieldNames", modelName=model_name)
            return cast("list[str]", raw_fields)
        except Exception:  # noqa: BLE001
            logger.debug(
                "AnkiConnect.get_model_field_names: model not found or error "
                "(model=%s)",
                model_name,
                exc_info=True,
            )
            return None

    def store_media_file(self, filename: str, file_path: str) -> None:
        import base64
        with open(file_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        self._invoke("storeMediaFile", filename=filename, data=data)

    def note_cards(self, note_ids: list[int]) -> dict[int, NoteCards]:
        intervals: dict[int, list[int]] = {}
        suspended: dict[int, int] = {}
        for card in self._cards_of(note_ids):
            note = int(cast("int", card["note"]))
            intervals.setdefault(note, [])
            suspended.setdefault(note, 0)
            if card["queue"] == _SUSPENDED_QUEUE:
                suspended[note] += 1
            else:
                intervals[note].append(int(cast("int", card["interval"])))
        return {
            note: NoteCards(intervals=tuple(intervals[note]), suspended=suspended[note])
            for note in intervals
        }

    def _cards_of(self, note_ids: list[int]) -> list[dict[str, object]]:
        """`cardsInfo` of every card of the notes, asked in batches."""
        card_ids: list[int] = []
        for notes in _batches(note_ids):
            query = "nid:" + ",".join(str(note) for note in notes)
            card_ids.extend(cast("list[int]", self._invoke("findCards", query=query) or []))
        cards: list[dict[str, object]] = []
        for batch in _batches(card_ids):
            cards.extend(cast("list[dict[str, object]]", self._invoke("cardsInfo", cards=batch)))
        return cards


def _batches(ids: list[int]) -> list[list[int]]:
    return [ids[start:start + ANKI_BATCH_SIZE] for start in range(0, len(ids), ANKI_BATCH_SIZE)]
