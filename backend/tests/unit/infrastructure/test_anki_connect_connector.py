from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import httpx
import pytest
from backend.infrastructure.adapters.anki_connect_connector import AnkiConnectConnector

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
            assert connector.find_notes_by_target("deck", "procrastinate") == [
                1,
                2,
                3,
            ]

    def test_returns_empty_list_when_invoke_returns_none(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=None):
            assert connector.find_notes_by_target("deck", "t") == []

    def test_returns_empty_list_when_invoke_returns_empty(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=[]):
            assert connector.find_notes_by_target("deck", "t") == []

    def test_query_uses_target_and_model_name(self) -> None:
        connector = AnkiConnectConnector(url="http://test")
        with patch.object(connector, "_invoke", return_value=[]) as invoke:
            connector.find_notes_by_target("deck", "give up")
        invoke.assert_called_once()
        assert invoke.call_args.args[0] == "findNotes"
        query = invoke.call_args.kwargs["query"]
        assert 'Target:"give up"' in query
        assert "note:AnythingToAnkiType" in query


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
