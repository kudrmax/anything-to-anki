from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
from backend.application.utils.export_queue import ExportQueue
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.export_group import ExportGroup
from backend.domain.value_objects.word_status import WordStatus

from tests.export_support import ExportCards, export_card
from tests.phrase_support import phrase
from tests.unit.application.scope_fakes import empty_scope_resolver

if TYPE_CHECKING:
    from pathlib import Path


class _EveryField(list[str]):
    """Fields of a note type that has every field the export asks for."""

    def __contains__(self, name: object) -> bool:
        return True


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
        cards = ExportCards()
        anki_connector = MagicMock()
        settings_repo = MagicMock()
        anki_sync_repo = MagicMock()
        renderer = AnkiTemplateRenderer(templates_dir)

        settings_repo.get.side_effect = lambda key, default: default

        candidate = export_card(
            StoredCandidate(
                id=1,
                source_id=1,
                lemma="test",
                pos="NOUN",
                cefr_level="B2",
                zipf_frequency=3.5,
                occurrences=1,
                status=WordStatus.LEARN,
            ),
            phrase("This is a test", "test"),
            meaning=CandidateMeaning(
                candidate_id=1, meaning="a trial", translation=None, synonyms=None,
                examples=None, ipa="/tɛst/", generated_at=None,
            ),
            tts=CandidateTTS(candidate_id=1, audio_path="/tmp/test.m4a", generated_at=None),
        )
        cards.put([candidate])

        anki_connector.is_available.return_value = True
        anki_connector.get_model_field_names.return_value = _EveryField()
        anki_sync_repo.get_synced_phrase_ids.return_value = set()
        anki_connector.add_notes.return_value = [12345]

        use_case = SyncToAnkiUseCase(
            export_queue=ExportQueue(
                cards.words, anki_sync_repo, cards,
            ),
            anki_connector=anki_connector,
            settings_repo=settings_repo,
            anki_sync_repo=anki_sync_repo,
            template_renderer=renderer,
            anki_note_repo=MagicMock(),
            cloze_builder=ClozeBuilder(),
            scope_resolver=empty_scope_resolver(),
        )
        use_case.execute(source_id=1, group=ExportGroup.READY)

        anki_connector.ensure_note_type.assert_called_once()
        call_kwargs = anki_connector.ensure_note_type.call_args
        assert call_kwargs.kwargs["front_template"] == "FRONT {{edit:Sentence}}"
        assert call_kwargs.kwargs["back_template"] == "BACK {{edit:Target}}"
        assert call_kwargs.kwargs["css"] == ".card { color: red; }"
