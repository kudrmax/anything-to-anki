from __future__ import annotations

import base64
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import httpx
import pytest
from backend.infrastructure.adapters.anki_connect_connector import AnkiConnectConnector

if TYPE_CHECKING:
    from pathlib import Path

_HTTPX_POST = "backend.infrastructure.adapters.anki_connect_connector.httpx.post"


def _httpx_ok(json_data: dict[str, object]) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.unit
class TestInvoke:
    def test_posts_correct_payload_and_returns_result_field(self) -> None:
        connector = AnkiConnectConnector(url="http://test:8765")
        with patch(
            _HTTPX_POST, return_value=_httpx_ok({"result": 6, "error": None})
        ) as post:
            result = connector.get_version()

        assert result == 6
        post.assert_called_once()
        args = post.call_args
        assert args.args[0] == "http://test:8765"
        payload = args.kwargs["json"]
        assert payload["action"] == "version"
        assert payload["version"] == 6
        assert payload["params"] == {}
        assert args.kwargs["timeout"] == 5.0

    def test_raises_runtime_error_on_anki_error_field(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch(
            _HTTPX_POST,
            return_value=_httpx_ok({"result": None, "error": "deck missing"}),
        ), pytest.raises(RuntimeError) as exc:
            connector.get_version()
        assert "deck missing" in str(exc.value)
        assert "AnkiConnect error" in str(exc.value)

    def test_propagates_http_status_error(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        resp = MagicMock(spec=httpx.Response)
        resp.json.return_value = {}
        resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "err", request=MagicMock(), response=MagicMock(status_code=500),
            )
        )
        with patch(_HTTPX_POST, return_value=resp), pytest.raises(
            httpx.HTTPStatusError
        ):
            connector.get_version()


@pytest.mark.unit
class TestIsAvailable:
    def test_returns_true_when_version_succeeds(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=6):
            assert connector.is_available() is True

    def test_returns_false_on_connect_error(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(
            connector, "_invoke", side_effect=httpx.ConnectError("refused")
        ):
            assert connector.is_available() is False

    def test_returns_false_on_runtime_error(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(
            connector, "_invoke", side_effect=RuntimeError("anki error: x")
        ):
            assert connector.is_available() is False


@pytest.mark.unit
class TestEnsureDeck:
    def test_calls_create_deck_action(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke") as invoke:
            connector.ensure_deck("My Deck")
        invoke.assert_called_once_with("createDeck", deck="My Deck")


@pytest.mark.unit
class TestFindNotesByTarget:
    def test_returns_list_when_notes_found(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=[1, 2, 3]):
            assert connector.find_notes_by_target(
                "deck", "AnythingToAnkiType", "Target", "procrastinate"
            ) == [
                1,
                2,
                3,
            ]

    def test_returns_empty_list_when_invoke_returns_none(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=None):
            assert connector.find_notes_by_target("deck", "M", "Target", "t") == []

    def test_returns_empty_list_when_invoke_returns_empty(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=[]):
            assert connector.find_notes_by_target("deck", "M", "Target", "t") == []

    def test_query_uses_target_and_model_name(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=[]) as invoke:
            connector.find_notes_by_target("deck", "AnythingToAnkiCloze", "Target", "give up")
        invoke.assert_called_once_with(
            "findNotes", query='note:"AnythingToAnkiCloze" "Target:give up"'
        )

    def test_query_uses_custom_model_and_target_field(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=[]) as invoke:
            connector.find_notes_by_target("deck", "My Words", "Word", "burnout")
        invoke.assert_called_once_with("findNotes", query='note:"My Words" "Word:burnout"')

    def test_query_escapes_quotes_in_target(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=[]) as invoke:
            connector.find_notes_by_target("deck", "M", "Target", 'say "hi"')
        assert invoke.call_args.kwargs["query"] == 'note:"M" "Target:say \\"hi\\""'

    def test_query_quotes_field_name_with_spaces(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=[]) as invoke:
            connector.find_notes_by_target("deck", "My Words", "Target Word", "burnout")
        assert invoke.call_args.kwargs["query"] == 'note:"My Words" "Target Word:burnout"'

    def test_query_escapes_wildcards_in_target(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=[]) as invoke:
            connector.find_notes_by_target("deck", "M", "Target", "a*b_c")
        assert invoke.call_args.kwargs["query"] == 'note:"M" "Target:a\\*b\\_c"'

    def test_query_escapes_backslashes(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=[]) as invoke:
            connector.find_notes_by_target("deck", "M\\1", "Tar\\get", "a\\b")
        assert invoke.call_args.kwargs["query"] == 'note:"M\\\\1" "Tar\\\\get:a\\\\b"'


@pytest.mark.unit
class TestAddNotes:
    def test_wraps_each_note_with_options_and_tags(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        fields_a = {"Sentence": "I procrastinate", "Target": "procrastinate"}
        fields_b = {"Sentence": "I give up", "Target": "give up"}
        with patch.object(
            connector, "_invoke", return_value=[101, 102]
        ) as invoke:
            result = connector.add_notes(
                "Default", "AnythingToAnkiType", [fields_a, fields_b]
            )

        assert result == [101, 102]
        invoke.assert_called_once()
        assert invoke.call_args.args[0] == "addNotes"
        notes_arg = invoke.call_args.kwargs["notes"]
        assert len(notes_arg) == 2
        for n, f in zip(notes_arg, [fields_a, fields_b], strict=True):
            assert n["deckName"] == "Default"
            assert n["modelName"] == "AnythingToAnkiType"
            assert n["fields"] == f
            assert n["options"] == {"allowDuplicate": False}
            assert n["tags"] == ["anything-to-anki"]

    def test_returns_ids_with_none_entries_intact(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(
            connector, "_invoke", return_value=[101, None, 102]
        ):
            result = connector.add_notes("d", "m", [{}, {}, {}])
        assert result == [101, None, 102]

    def test_returns_empty_list_when_invoke_returns_none(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=None):
            assert connector.add_notes("d", "m", [{}]) == []


@pytest.mark.unit
class TestGetModelFieldNames:
    def test_returns_fields_when_model_present(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke") as invoke:
            invoke.side_effect = [
                ["OtherModel", "MyType"],  # modelNames
                ["Sentence", "Target", "Meaning"],  # modelFieldNames
            ]
            result = connector.get_model_field_names("MyType")
        assert result == ["Sentence", "Target", "Meaning"]

    def test_returns_none_when_model_missing(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=["Other"]):
            assert connector.get_model_field_names("MyType") is None

    def test_returns_none_on_invoke_error(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(
            connector, "_invoke", side_effect=RuntimeError("err")
        ):
            assert connector.get_model_field_names("MyType") is None


@pytest.mark.unit
class TestStoreMediaFile:
    def test_base64_encodes_file_content(self, tmp_path: Path) -> None:
        connector = AnkiConnectConnector(url="http://test")
        file_path = tmp_path / "img.png"
        file_path.write_bytes(b"PNGDATA!!")
        expected_b64 = base64.b64encode(b"PNGDATA!!").decode()

        with patch.object(connector, "_invoke") as invoke:
            connector.store_media_file("img.png", str(file_path))

        invoke.assert_called_once_with(
            "storeMediaFile", filename="img.png", data=expected_b64
        )


@pytest.mark.unit
class TestEnsureNoteType:
    def test_creates_model_when_missing(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke") as invoke:
            invoke.side_effect = [
                ["OtherModel"],   # modelNames
                None,              # createModel
            ]
            connector.ensure_note_type("MyType", ["A", "B", "C"])

        assert invoke.call_args_list[0] == call("modelNames")
        create_call = invoke.call_args_list[1]
        assert create_call.args[0] == "createModel"
        assert create_call.kwargs["modelName"] == "MyType"
        assert create_call.kwargs["inOrderFields"] == ["A", "B", "C"]

    def test_adds_missing_fields_when_model_exists(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke") as invoke:
            invoke.side_effect = [
                ["MyType"],        # modelNames — present
                ["A", "B"],        # modelFieldNames
                None,               # modelFieldAdd C
                None,               # modelFieldAdd D
            ]
            connector.ensure_note_type("MyType", ["A", "B", "C", "D"])

        invoke.assert_any_call("modelFieldNames", modelName="MyType")
        invoke.assert_any_call("modelFieldAdd", modelName="MyType", fieldName="C", index=2)
        invoke.assert_any_call("modelFieldAdd", modelName="MyType", fieldName="D", index=3)
        for c in invoke.call_args_list:
            assert c.args[0] != "createModel"

    def test_noop_when_all_fields_present(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke") as invoke:
            invoke.side_effect = [
                ["MyType"],
                ["A", "B", "C"],
            ]
            connector.ensure_note_type("MyType", ["A", "B"])

        assert invoke.call_count == 2
        for c in invoke.call_args_list:
            assert c.args[0] in ("modelNames", "modelFieldNames")

    def test_does_not_remove_existing_extra_fields(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke") as invoke:
            invoke.side_effect = [
                ["MyType"],
                ["A", "B", "Z"],
                None,
            ]
            connector.ensure_note_type("MyType", ["A", "B", "C"])

        for c in invoke.call_args_list:
            assert c.args[0] not in ("modelFieldRemove",)

    def test_creates_standard_model_by_default(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke") as invoke:
            invoke.side_effect = [[], None]
            connector.ensure_note_type("MyType", ["A"])

        create_call = invoke.call_args_list[1]
        assert create_call.kwargs["isCloze"] is False
        assert create_call.kwargs["cardTemplates"][0]["Name"] == "AnythingToAnki Card"

    def test_creates_cloze_model(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke") as invoke:
            invoke.side_effect = [[], None]
            connector.ensure_note_type(
                "AnythingToAnkiCloze",
                ["Text", "Target"],
                front_template="{{cloze:Text}}",
                back_template="{{cloze:Text}}{{Target}}",
                css=".card {}",
                is_cloze=True,
            )

        create_call = invoke.call_args_list[1]
        assert create_call.args[0] == "createModel"
        assert create_call.kwargs["isCloze"] is True
        assert create_call.kwargs["cardTemplates"] == [
            {
                "Name": "AnythingToAnki Cloze",
                "Front": "{{cloze:Text}}",
                "Back": "{{cloze:Text}}{{Target}}",
            }
        ]


class _FakeAnkiCards:
    """AnkiConnect's `findCards nid:` and `cardsInfo` over a fixed set of cards."""

    def __init__(self, cards: dict[int, tuple[int, int, int]]) -> None:
        self.cards = cards  # card id → (note id, interval, queue)
        self.calls: list[tuple[str, dict[str, object]]] = []

    def invoke(self, action: str, **params: object) -> object:
        self.calls.append((action, params))
        if action == "findCards":
            query = str(params["query"])
            assert query.startswith("nid:")
            notes = {int(n) for n in query.removeprefix("nid:").split(",")}
            return [card for card, (note, _, _) in self.cards.items() if note in notes]
        assert action == "cardsInfo"
        card_ids = params["cards"]
        assert isinstance(card_ids, list)
        return [
            {"cardId": card, "note": self.cards[card][0], "interval": self.cards[card][1],
             "queue": self.cards[card][2]}
            for card in card_ids
        ]


@pytest.mark.unit
class TestNoteCards:
    def _connector(self, fake: _FakeAnkiCards) -> AnkiConnectConnector:
        connector = AnkiConnectConnector(url="http://test")
        connector._invoke = fake.invoke  # type: ignore[method-assign]
        return connector

    def test_gives_the_active_intervals_and_suspended_count_of_each_note(self) -> None:
        fake = _FakeAnkiCards({
            11: (1, 30, 2), 12: (1, -600, 1), 13: (1, 50, -1),
            21: (2, 25, 2),
        })

        cards = self._connector(fake).note_cards([1, 2])

        assert sorted(cards[1].intervals) == [-600, 30]
        assert cards[1].suspended == 1
        assert cards[2].intervals == (25,)
        assert cards[2].suspended == 0

    def test_a_note_without_cards_is_missing(self) -> None:
        fake = _FakeAnkiCards({11: (1, 30, 2)})

        assert set(self._connector(fake).note_cards([1, 2])) == {1}

    def test_no_notes_ask_nothing(self) -> None:
        fake = _FakeAnkiCards({})

        assert self._connector(fake).note_cards([]) == {}
        assert fake.calls == []

    def test_asks_in_batches(self) -> None:
        notes = list(range(1, 502))
        fake = _FakeAnkiCards({note * 10: (note, 30, 2) for note in notes})

        cards = self._connector(fake).note_cards(notes)

        assert len(cards) == 501
        finds = [params for action, params in fake.calls if action == "findCards"]
        infos = [params for action, params in fake.calls if action == "cardsInfo"]
        assert len(finds) == 2
        assert all(len(info["cards"]) <= 500 for info in infos)  # type: ignore[arg-type]
