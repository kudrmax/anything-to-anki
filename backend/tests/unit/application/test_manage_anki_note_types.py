from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.manage_anki_note_types import ManageAnkiNoteTypesUseCase
from backend.application.utils.anki_template_renderer import NoteTemplates
from backend.domain.exceptions import AnkiNotAvailableError

pytestmark = pytest.mark.unit


class _Fixture:
    def __init__(self, existing: dict[str, list[str]], settings: dict[str, str]) -> None:
        self.connector = MagicMock()
        self.connector.is_available.return_value = True
        self.connector.get_model_field_names.side_effect = existing.get
        settings_repo = MagicMock()
        settings_repo.get.side_effect = lambda key, default=None: settings.get(key)
        renderer = MagicMock()
        renderer.render_recognition.return_value = NoteTemplates("F", "B", "C")
        renderer.render_cloze.return_value = NoteTemplates("CF", "CB", "C")
        self.use_case = ManageAnkiNoteTypesUseCase(self.connector, settings_repo, renderer)


class TestVerify:
    def test_valid_when_both_types_have_every_field(self) -> None:
        recognition = ["Sentence", "Target", "Meaning", "IPA", "Translation", "Synonyms",
                       "Examples", "Image", "MeaningImage", "Audio",
                       "AudioTargetUS", "AudioTargetUK", "AudioTTS"]
        fx = _Fixture(
            {"AnythingToAnkiType": recognition, "AnythingToAnkiCloze": [*recognition, "Hint"]},
            {},
        )

        result = fx.use_case.verify()

        assert result.valid is True
        assert [check.missing_fields for check in result.note_types] == [[], []]

    def test_cloze_type_needs_the_hint_and_the_shared_fields(self) -> None:
        fx = _Fixture({"Main": ["Phrase"], "Main Cloze": ["Phrase"]}, {
            "anki_note_type": "Main",
            "anki_cloze_note_type": "Main Cloze",
            "anki_field_sentence": "Phrase",
        })

        recognition, cloze = fx.use_case.verify().note_types

        assert "Hint" not in recognition.missing_fields
        assert "Hint" in cloze.missing_fields
        assert "MeaningImage" in cloze.missing_fields

    def test_anki_unavailable(self) -> None:
        fx = _Fixture({}, {})
        fx.connector.is_available.return_value = False

        with pytest.raises(AnkiNotAvailableError):
            fx.use_case.verify()


class TestCreate:
    def test_user_types_get_the_missing_fields_too(self) -> None:
        fx = _Fixture({"Main": ["Sentence"]}, {"anki_note_type": "Main"})

        result = fx.use_case.create()

        assert result.created == ["AnythingToAnkiCloze"]
        ensured = {c.args[0]: c.kwargs.get("is_cloze", False)
                   for c in fx.connector.ensure_note_type.call_args_list}
        assert ensured == {"Main": False, "AnythingToAnkiCloze": True}
