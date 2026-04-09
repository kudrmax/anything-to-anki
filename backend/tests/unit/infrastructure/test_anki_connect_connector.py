from __future__ import annotations

from unittest.mock import call, patch

import pytest
from backend.infrastructure.adapters.anki_connect_connector import AnkiConnectConnector


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
