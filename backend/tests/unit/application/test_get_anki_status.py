from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_anki_status import GetAnkiStatusUseCase


def _use_case(
    available: bool, fields: dict[str, list[str]], settings: dict[str, str],
) -> GetAnkiStatusUseCase:
    connector = MagicMock()
    connector.is_available.return_value = available
    connector.get_model_field_names.side_effect = fields.get
    settings_repo = MagicMock()
    settings_repo.get.side_effect = lambda key, default=None: settings.get(key)
    return GetAnkiStatusUseCase(connector, settings_repo, MagicMock())


@pytest.mark.unit
class TestGetAnkiStatusUseCase:
    def test_not_available(self) -> None:
        result = _use_case(False, {}, {}).execute()
        assert result.available is False
        assert result.note_type_problems == []

    def test_app_note_types_are_no_problem_the_export_creates_them(self) -> None:
        result = _use_case(True, {}, {}).execute()
        assert result.available is True
        assert result.note_type_problems == []

    def test_users_note_type_missing_fields_is_a_problem(self) -> None:
        result = _use_case(
            True, {"Main": ["Sentence", "Target"]}, {"anki_note_type": "Main"},
        ).execute()

        [problem] = result.note_type_problems
        assert problem.note_type == "Main"
        assert problem.exists is True
        assert "AudioTTS" in problem.missing_fields
        assert "Sentence" not in problem.missing_fields

    def test_users_cloze_type_missing_is_a_problem(self) -> None:
        result = _use_case(True, {}, {"anki_cloze_note_type": "Main Cloze"}).execute()

        [problem] = result.note_type_problems
        assert (problem.note_type, problem.exists) == ("Main Cloze", False)
