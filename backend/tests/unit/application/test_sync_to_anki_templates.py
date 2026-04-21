from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
from backend.domain.value_objects.candidate_status import CandidateStatus


@pytest.fixture()
def templates_dir(tmp_path: Path) -> Path:
    (tmp_path / "front.html").write_text("FRONT {{edit:%FIELD_SENTENCE%}}")
    (tmp_path / "back.html").write_text("BACK {{edit:%FIELD_TARGET%}}")
    (tmp_path / "style.css").write_text(".card { color: red; }")
    return tmp_path


class TestSyncToAnkiTemplates:
    def test_passes_rendered_templates_to_ensure_note_type(
        self, templates_dir: Path
    ) -> None:
        candidate_repo = MagicMock()
        anki_connector = MagicMock()
        settings_repo = MagicMock()
        anki_sync_repo = MagicMock()
        renderer = AnkiTemplateRenderer(templates_dir)

        settings_repo.get.side_effect = lambda key, default: default

        candidate = MagicMock()
        candidate.id = 1
        candidate.status = CandidateStatus.LEARN
        candidate.lemma = "test"
        candidate.surface_form = None
        candidate.context_fragment = "This is a test"
        candidate.meaning = MagicMock()
        candidate.meaning.meaning = "a trial"
        candidate.meaning.ipa = "/tɛst/"
        candidate.meaning.translation = None
        candidate.meaning.synonyms = None
        candidate.meaning.examples = None
        candidate.media = None
        candidate_repo.get_by_source.return_value = [candidate]

        anki_connector.is_available.return_value = True
        anki_sync_repo.get_synced_candidate_ids.return_value = set()
        anki_connector.add_notes.return_value = [12345]

        known_word_repo = MagicMock()
        use_case = SyncToAnkiUseCase(
            candidate_repo=candidate_repo,
            anki_connector=anki_connector,
            settings_repo=settings_repo,
            anki_sync_repo=anki_sync_repo,
            template_renderer=renderer,
            known_word_repo=known_word_repo,
        )
        use_case.execute(source_id=1)

        anki_connector.ensure_note_type.assert_called_once()
        call_kwargs = anki_connector.ensure_note_type.call_args
        assert call_kwargs.kwargs["front_template"] == "FRONT {{edit:Sentence}}"
        assert call_kwargs.kwargs["back_template"] == "BACK {{edit:Target}}"
        assert call_kwargs.kwargs["css"] == ".card { color: red; }"
