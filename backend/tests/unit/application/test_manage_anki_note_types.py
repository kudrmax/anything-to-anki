from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.manage_anki_note_types import ManageAnkiNoteTypesUseCase
from backend.application.utils.anki_note_types import NoteTypeKind
from backend.application.utils.anki_template_renderer import NoteTemplates
from backend.domain.exceptions import AnkiNotAvailableError

pytestmark = pytest.mark.unit

RECOGNITION_FIELDS = [
    "Sentence", "Target", "Meaning", "IPA", "Translation", "Synonyms", "Examples",
    "Image", "MeaningImage", "Audio", "AudioTargetUS", "AudioTargetUK", "AudioTTS",
]


class _Anki:
    """Note types in a fake Anki: ensure_note_type creates a type or adds the missing fields."""

    def __init__(self, note_types: dict[str, list[str]]) -> None:
        self.note_types = note_types
        self.connector = MagicMock()
        self.connector.is_available.return_value = True
        self.connector.get_model_field_names.side_effect = note_types.get
        self.connector.ensure_note_type.side_effect = self._ensure

    def _ensure(self, name: str, fields: list[str], **_: object) -> None:
        current = self.note_types.setdefault(name, [])
        current.extend(field for field in fields if field not in current)


def _use_case(anki: _Anki, settings: dict[str, str]) -> ManageAnkiNoteTypesUseCase:
    settings_repo = MagicMock()
    settings_repo.get.side_effect = lambda key, default=None: settings.get(key)
    renderer = MagicMock()
    renderer.render_recognition.return_value = NoteTemplates("F", "B", "C")
    renderer.render_cloze.return_value = NoteTemplates("CF", "CB", "C")
    return ManageAnkiNoteTypesUseCase(anki.connector, settings_repo, renderer)


class TestCheck:
    def test_ready_types_need_no_fix(self) -> None:
        anki = _Anki({
            "AnythingToAnkiType": list(RECOGNITION_FIELDS),
            "AnythingToAnkiCloze": [*RECOGNITION_FIELDS, "Hint"],
        })

        checks = _use_case(anki, {}).check()

        assert [(c.kind, c.fix) for c in checks] == [("recognition", None), ("cloze", None)]

    def test_each_type_says_what_fixes_it(self) -> None:
        anki = _Anki({"Main": ["Sentence"]})

        recognition, cloze = _use_case(anki, {"anki_note_type": "Main"}).check()

        assert (recognition.note_type, recognition.fix) == ("Main", "add_fields")
        assert "AudioTTS" in recognition.missing_fields
        assert (cloze.note_type, cloze.fix) == ("AnythingToAnkiCloze", "create")

    def test_anki_unavailable(self) -> None:
        anki = _Anki({})
        anki.connector.is_available.return_value = False

        with pytest.raises(AnkiNotAvailableError):
            _use_case(anki, {}).check()


class TestFix:
    def test_adds_only_the_missing_fields_to_that_type(self) -> None:
        anki = _Anki({"Main": ["Sentence", "Target"]})

        result = _use_case(anki, {"anki_note_type": "Main"}).fix(NoteTypeKind.RECOGNITION)

        assert result.fix is None
        assert anki.note_types["Main"][:2] == ["Sentence", "Target"]
        assert "AnythingToAnkiCloze" not in anki.note_types

    def test_creates_a_cloze_type_that_is_not_in_anki(self) -> None:
        anki = _Anki({})

        result = _use_case(anki, {}).fix(NoteTypeKind.CLOZE)

        assert (result.note_type, result.fix) == ("AnythingToAnkiCloze", None)
        anki.connector.ensure_note_type.assert_called_once()
        assert anki.connector.ensure_note_type.call_args.kwargs["is_cloze"] is True
