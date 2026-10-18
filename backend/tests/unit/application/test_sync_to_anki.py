from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.application.utils.anki_template_renderer import NoteTemplates
from backend.application.utils.export_queue import ExportCard, ExportQueue
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import AnkiNotAvailableError, AnkiNoteTypeIncompleteError
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.export_group import ExportGroup
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.word_status import WordStatus

from tests.export_support import ExportCards, export_card, with_phrase, with_word
from tests.phrase_support import phrase
from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.scope_fakes import empty_scope_resolver
from tests.unit.application.source_fakes import InMemorySourceRepository
from tests.word_support import phrase_id_of


class _EveryField(list[str]):
    """Fields of a note type that has every field the export asks for."""

    def __contains__(self, name: object) -> bool:
        return True


def _make_candidate(
    candidate_id: int,
    lemma: str,
    status: WordStatus,
    meaning: str | None = None,
    ipa: str | None = None,
    translation: str | None = None,
    synonyms: str | None = None,
    examples: str | None = None,
    source_id: int = 1,
    tts_path: str | None = "/tmp/tts.mp3",
) -> ExportCard:
    meaning_obj = None
    if any(v is not None for v in (meaning, ipa, translation, synonyms, examples)):
        meaning_obj = CandidateMeaning(
            candidate_id=candidate_id,
            meaning=meaning,
            translation=translation,
            synonyms=synonyms,
            examples=examples,
            ipa=ipa,
            generated_at=datetime(2026, 4, 7, tzinfo=UTC),
        )
    return export_card(
        StoredCandidate(
            id=candidate_id,
            source_id=source_id,
            lemma=lemma,
            pos="NOUN",
            cefr_level="B2",
            zipf_frequency=3.5,
            occurrences=1,
            status=status,
        ),
        phrase(f"context with {lemma} here", lemma),
        meaning=meaning_obj,
        media=None,
        tts=CandidateTTS(candidate_id=candidate_id, audio_path=tts_path, generated_at=None),
    )


@pytest.mark.unit
class TestSyncToAnkiUseCase:
    def setup_method(self) -> None:
        self.cards = ExportCards()
        self.anki_connector = MagicMock()
        self.settings_repo = MagicMock()
        self.anki_sync_repo = MagicMock()
        self.template_renderer = MagicMock()
        self.anki_note_repo = MagicMock()
        self.known_from_anki = MagicMock()
        self.known_from_anki.run.return_value = 0
        self.template_renderer.render_recognition.return_value = NoteTemplates(
            "<front/>", "<back/>", "",
        )
        self.settings_repo.get.return_value = None  # use default deck
        self.anki_connector.get_model_field_names.return_value = _EveryField()
        self.anki_sync_repo.get_synced_phrase_ids.return_value = set()
        self.use_case = SyncToAnkiUseCase(
            export_queue=ExportQueue(
                self.cards.words, self.anki_sync_repo, self.cards,
            ),
            anki_connector=self.anki_connector,
            settings_repo=self.settings_repo,
            anki_sync_repo=self.anki_sync_repo,
            template_renderer=self.template_renderer,
            anki_note_repo=self.anki_note_repo,
            known_from_anki=self.known_from_anki,
            cloze_builder=ClozeBuilder(),
            scope_resolver=empty_scope_resolver(),
        )

    def test_returns_zero_when_no_learn_candidates(self) -> None:
        self.cards.put([
            _make_candidate(1, "word", WordStatus.NEW),
        ])
        result = self.use_case.execute(source_id=1, group=ExportGroup.READY)
        assert result.total == 0
        assert result.added == 0
        self.anki_connector.add_notes.assert_not_called()

    def test_raises_when_anki_unavailable(self) -> None:
        self.cards.put([
            _make_candidate(1, "word", WordStatus.LEARN),
        ])
        self.anki_connector.is_available.return_value = False
        with pytest.raises(AnkiNotAvailableError):
            self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

    def test_adds_new_cards(self) -> None:
        self.cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN, meaning="выгорание"),
            _make_candidate(2, "relentless", WordStatus.LEARN, meaning="неумолимый"),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        result = self.use_case.execute(source_id=1, group=ExportGroup.READY)

        assert result.total == 2
        assert result.added == 2
        assert result.skipped == 0
        assert result.errors == 0
        assert self.anki_note_repo.add.call_count == 2
        self.anki_note_repo.add.assert_any_call(12345, "burnout", "NOUN")
        self.anki_note_repo.add.assert_any_call(12345, "relentless", "NOUN")

    def test_exports_only_not_yet_exported_candidates(self) -> None:
        self.cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN),
            _make_candidate(2, "relentless", WordStatus.LEARN),
        ])
        # burnout already exported
        self.anki_sync_repo.get_synced_phrase_ids.return_value = {phrase_id_of(1)}
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [99999]

        result = self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        assert result.total == 1
        assert result.added == 1
        assert result.skipped == 0
        assert result.skipped_lemmas == []
        self.anki_connector.add_notes.assert_called_once()
        call_notes = self.anki_connector.add_notes.call_args[1]["notes"]
        assert call_notes[0]["Target"] == "relentless"
        self.anki_note_repo.add.assert_called_once_with(99999, "relentless", "NOUN")

    def test_all_already_exported_returns_without_calling_anki(self) -> None:
        self.cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN),
        ])
        self.anki_sync_repo.get_synced_phrase_ids.return_value = {phrase_id_of(1)}

        result = self.use_case.execute(source_id=1, group=ExportGroup.READY)

        assert result.total == 0
        assert result.added == 0
        assert result.skipped == 0
        self.anki_connector.add_notes.assert_not_called()
        self.anki_note_repo.add.assert_not_called()

    def test_marks_synced_after_successful_add(self) -> None:
        self.cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        self.anki_sync_repo.mark_synced.assert_called_once_with(1, 12345, phrase_id_of(1))
        self.anki_note_repo.add.assert_called_once_with(12345, "burnout", "NOUN")

    def test_counts_as_skipped_when_note_already_exists_in_anki(self) -> None:
        # add_notes returns None (allowDuplicate=False), but note exists in Anki
        self.cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [None]
        self.anki_connector.find_notes_by_target.return_value = [99999]

        result = self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        assert result.added == 0
        assert result.skipped == 1
        assert result.skipped_lemmas == ["burnout"]
        assert result.errors == 0
        self.anki_sync_repo.mark_synced.assert_called_once_with(1, 99999, phrase_id_of(1))
        self.anki_note_repo.add.assert_called_once_with(99999, "burnout", "NOUN")

    def test_counts_errors_when_add_fails_and_note_not_found(self) -> None:
        self.cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [None]
        self.anki_connector.find_notes_by_target.return_value = []

        result = self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        assert result.added == 0
        assert result.errors == 1
        assert result.error_lemmas == ["burnout"]
        self.anki_sync_repo.mark_synced.assert_not_called()
        self.anki_note_repo.add.assert_not_called()

    def test_duplicate_exception_marks_synced_and_counts_as_skipped(self) -> None:
        self.cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.side_effect = RuntimeError(
            "AnkiConnect error: ['cannot create note because it is a duplicate']"
        )
        self.anki_connector.find_notes_by_target.return_value = [99999]

        result = self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        assert result.added == 0
        assert result.skipped == 1
        assert result.skipped_lemmas == ["burnout"]
        assert result.errors == 0
        self.anki_sync_repo.mark_synced.assert_called_once_with(1, 99999, phrase_id_of(1))
        self.anki_note_repo.add.assert_called_once_with(99999, "burnout", "NOUN")

    def test_counts_errors_on_exception(self) -> None:
        self.cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.side_effect = RuntimeError("some unexpected error")

        result = self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        assert result.added == 0
        assert result.errors == 1
        assert result.error_lemmas == ["burnout"]
        self.anki_sync_repo.mark_synced.assert_not_called()
        self.anki_note_repo.add.assert_not_called()

    def test_meaning_from_candidate(self) -> None:
        self.cards.put([
            _make_candidate(1, "thug", WordStatus.LEARN, meaning="бандит, головорез"),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.READY)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert note[0]["Meaning"] == "бандит, головорез"

    def test_no_meaning_becomes_empty_string(self) -> None:
        self.cards.put([
            _make_candidate(1, "thug", WordStatus.LEARN, meaning=None),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert note[0]["Meaning"] == ""

    def test_ipa_from_candidate(self) -> None:
        self.cards.put([
            _make_candidate(1, "thug", WordStatus.LEARN, ipa="/θʌɡ/"),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert note[0]["IPA"] == "/θʌɡ/"

    def test_image_field_populated_when_media_present(self) -> None:
        candidate = with_phrase(
            _make_candidate(1, "thug", WordStatus.LEARN, meaning="бандит"),
            media=CandidateMedia(
                candidate_id=1,
                screenshot_path="/tmp/img.png",
                audio_path="/tmp/snd.mp3",
                start_ms=0,
                end_ms=1000,
                generated_at=datetime(2026, 4, 8, tzinfo=UTC),
            ),
        )
        self.cards.put([candidate])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        exists_path = "backend.application.utils.anki_note_builders.os.path.exists"
        with patch(exists_path, return_value=True):
            self.use_case.execute(source_id=1, group=ExportGroup.READY)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert note[0]["Image"] == '<img src="img.png">'
        assert note[0]["Audio"] == "[sound:snd.mp3]"
        # Connector should have stored the media files
        self.anki_connector.store_media_file.assert_any_call("img.png", "/tmp/img.png")
        self.anki_connector.store_media_file.assert_any_call("snd.mp3", "/tmp/snd.mp3")

    def test_frame_and_meaning_image_go_to_their_own_fields(self) -> None:
        candidate = _make_candidate(1, "drain", WordStatus.LEARN, meaning="слив")
        candidate = with_phrase(candidate, media=CandidateMedia(
            candidate_id=1, screenshot_path="/tmp/1_screenshot.webp", audio_path=None,
            start_ms=0, end_ms=1000, generated_at=None,
        ))
        candidate = with_word(candidate, meaning_image=CandidateMeaningImage(
            candidate_id=1, image_path="/tmp/1_meaning.0a1b2c3d4e.webp",
        ))
        self.cards.put([candidate])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        exists_path = "backend.application.utils.anki_note_builders.os.path.exists"
        with patch(exists_path, return_value=True):
            self.use_case.execute(source_id=1, group=ExportGroup.READY)

        note = self.anki_connector.add_notes.call_args.kwargs["notes"][0]
        assert note["Image"] == '<img src="1_screenshot.webp">'
        assert note["MeaningImage"] == '<img src="1_meaning.0a1b2c3d4e.webp">'

    def test_meaning_image_without_a_frame_leaves_the_front_picture_empty(self) -> None:
        candidate = _make_candidate(1, "drain", WordStatus.LEARN, meaning="слив")
        candidate = with_word(candidate, meaning_image=CandidateMeaningImage(
            candidate_id=1, image_path="/tmp/1_meaning.0a1b2c3d4e.webp",
        ))
        self.cards.put([candidate])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        exists_path = "backend.application.utils.anki_note_builders.os.path.exists"
        with patch(exists_path, return_value=True):
            self.use_case.execute(source_id=1, group=ExportGroup.READY)

        note = self.anki_connector.add_notes.call_args.kwargs["notes"][0]
        assert "Image" not in note
        assert note["MeaningImage"] == '<img src="1_meaning.0a1b2c3d4e.webp">'

    def test_image_audio_fields_absent_when_no_media(self) -> None:
        # _make_candidate constructs StoredCandidate with media=None
        self.cards.put([
            _make_candidate(1, "thug", WordStatus.LEARN, meaning="бандит"),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.READY)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert "Image" not in note[0]
        assert "Audio" not in note[0]
        self.anki_connector.store_media_file.assert_not_called()

    def test_all_scope_aggregates_results(self) -> None:
        """The all scope pushes the learn candidates of every source in one go."""
        candidate1 = _make_candidate(10, "burnout", WordStatus.LEARN, source_id=1)
        candidate2 = _make_candidate(20, "pursuit", WordStatus.LEARN, source_id=2)

        self.cards.put([candidate1, candidate2])
        self.anki_sync_repo.get_synced_phrase_ids.return_value = set()
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        result = self.use_case.execute_scope(SourceScope.all(), ExportGroup.INCOMPLETE)

        assert result.total == 2
        assert result.added == 2
        assert result.errors == 0

    def test_all_scope_skips_sources_with_everything_exported(self) -> None:
        exported = _make_candidate(10, "burnout", WordStatus.LEARN, source_id=1)
        fresh = _make_candidate(20, "pursuit", WordStatus.LEARN, source_id=2)

        self.cards.put([exported, fresh])
        self.anki_sync_repo.get_synced_phrase_ids.side_effect = (
            lambda ids: {phrase_id_of(10)} & set(ids)
        )
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        result = self.use_case.execute_scope(SourceScope.all(), ExportGroup.INCOMPLETE)

        assert result.total == 1
        assert result.added == 1
        notes = [c.kwargs["notes"][0]["Target"] for c in self._added_note_calls()]
        assert notes == ["pursuit"]

    def _added_note_calls(self) -> list[Any]:
        return list(self.anki_connector.add_notes.call_args_list)

    def test_exports_only_the_requested_group(self) -> None:
        self.cards.put([
            _make_candidate(1, "ready", WordStatus.LEARN, meaning="done"),
            _make_candidate(2, "no_meaning", WordStatus.LEARN),
            _make_candidate(3, "no_audio", WordStatus.LEARN, meaning="done", tts_path=None),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        ready = self.use_case.execute(source_id=1, group=ExportGroup.READY)
        notes = [c.kwargs["notes"][0]["Target"] for c in self._added_note_calls()]
        assert ready.total == 1
        assert notes == ["ready"]

        self.anki_connector.add_notes.reset_mock()
        incomplete = self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)
        notes = [c.kwargs["notes"][0]["Target"] for c in self._added_note_calls()]
        assert incomplete.total == 2
        assert notes == ["no_meaning", "no_audio"]

    def test_all_scope_empty_when_no_learn(self) -> None:
        self.cards.put([])
        result = self.use_case.execute_scope(SourceScope.all(), ExportGroup.READY)
        assert result.total == 0
        assert result.added == 0

    def test_translation_and_synonyms_from_candidate(self) -> None:
        self.cards.put([
            _make_candidate(
                1, "thug", WordStatus.LEARN,
                meaning="бандит",
                translation="бандит",
                synonyms="ruffian, gangster",
            ),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.READY)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert note[0]["Translation"] == "бандит"
        assert note[0]["Synonyms"] == "ruffian, gangster"

    def test_translation_synonyms_omitted_for_legacy_records(self) -> None:
        # Legacy candidate has meaning but translation and synonyms are NULL
        self.cards.put([
            _make_candidate(1, "thug", WordStatus.LEARN, meaning="бандит"),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.READY)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert "Translation" not in note[0]
        assert "Synonyms" not in note[0]

    def test_examples_formatted_as_bullet_list(self) -> None:
        self.cards.put([
            _make_candidate(
                1, "aisle", WordStatus.LEARN,
                meaning="проход",
                examples=(
                    "The bride walked down the **aisle**.\n"
                    "All guests stood at the end of the **aisle**."
                ),
            ),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.READY)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        examples = note[0]["Examples"]
        # markdown **aisle** stripped and re-wrapped with <b> by highlight_all_forms
        assert "**" not in examples
        assert "<b>aisle</b>" in examples
        # examples wrapped in <ul><li> bullet list
        assert "<ul>" in examples
        assert "<li>" in examples
        assert examples.count("<li>") == 2

    def test_translation_and_synonyms_formatted_with_highlight(self) -> None:
        self.cards.put([
            _make_candidate(
                1, "thug", WordStatus.LEARN,
                meaning="бандит",
                translation="бандит\nголоворез",
                synonyms="ruffian\ngangster",
            ),
        ])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.READY)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        # newlines converted to <br>
        assert note[0]["Translation"] == "бандит<br>головорез"
        assert note[0]["Synonyms"] == "ruffian<br>gangster"

    def test_image_field_skipped_when_file_missing(self) -> None:
        # Media is recorded but the file no longer exists on disk.
        candidate = export_card(
            StoredCandidate(
                id=1,
                source_id=1,
                lemma="thug",
                pos="NOUN",
                cefr_level="B2",
                zipf_frequency=3.5,
                occurrences=1,
                status=WordStatus.LEARN,
            ),
            phrase("context with thug here", "thug"),
            meaning=CandidateMeaning(
                candidate_id=1,
                meaning="бандит",
                translation=None,
                synonyms=None,
                examples=None,
                ipa=None,
                generated_at=datetime(2026, 4, 8, tzinfo=UTC),
            ),
            media=CandidateMedia(
                candidate_id=1,
                screenshot_path="/tmp/missing.png",
                audio_path="/tmp/missing.mp3",
                start_ms=0,
                end_ms=1000,
                generated_at=datetime(2026, 4, 8, tzinfo=UTC),
            ),
        )
        self.cards.put([candidate])
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        exists_path = "backend.application.utils.anki_note_builders.os.path.exists"
        with patch(exists_path, return_value=False):
            self.use_case.execute(source_id=1, group=ExportGroup.READY)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert "Image" not in note[0]
        assert "Audio" not in note[0]
        self.anki_connector.store_media_file.assert_not_called()


@pytest.mark.unit
class TestSyncRefusesIncompleteNoteType:
    def _use_case(self, model_fields: list[str] | None) -> tuple[SyncToAnkiUseCase, MagicMock]:
        cards = ExportCards()
        cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN, meaning="выгорание"),
        ])
        connector = MagicMock()
        connector.is_available.return_value = True
        connector.get_model_field_names.return_value = model_fields
        settings_repo = MagicMock()
        names = {"anki_note_type": "Main"}
        settings_repo.get.side_effect = lambda key, default=None: names.get(key)
        anki_sync_repo = MagicMock()
        anki_sync_repo.get_synced_phrase_ids.return_value = set()
        use_case = SyncToAnkiUseCase(
            export_queue=ExportQueue(
                cards.words, anki_sync_repo, cards,
            ),
            anki_connector=connector,
            settings_repo=settings_repo,
            anki_sync_repo=anki_sync_repo,
            template_renderer=MagicMock(),
            anki_note_repo=MagicMock(),
            known_from_anki=MagicMock(**{"run.return_value": 0}),
            cloze_builder=ClozeBuilder(),
            scope_resolver=empty_scope_resolver(),
        )
        return use_case, connector

    def test_a_missing_field_stops_the_export_before_any_card(self) -> None:
        use_case, connector = self._use_case(["Sentence", "Target", "Meaning"])

        with pytest.raises(AnkiNoteTypeIncompleteError) as error:
            use_case.execute(source_id=1, group=ExportGroup.READY)

        assert error.value.note_type == "Main"
        assert "AudioTTS" in error.value.missing_fields
        assert "AudioTTS" in str(error.value)
        connector.add_notes.assert_not_called()

    def test_a_missing_note_type_stops_the_export(self) -> None:
        use_case, connector = self._use_case(None)

        with pytest.raises(AnkiNoteTypeIncompleteError, match="is not in Anki"):
            use_case.execute(source_id=1, group=ExportGroup.READY)
        connector.add_notes.assert_not_called()


@pytest.mark.unit
class TestSyncCollectionScope:
    def test_sync_scope_pushes_only_scope_cards(self) -> None:
        cards = ExportCards()
        cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN, meaning="done", source_id=1),
            _make_candidate(2, "pursuit", WordStatus.LEARN, meaning="done", source_id=2),
        ])
        anki_sync_repo = MagicMock()
        anki_sync_repo.get_synced_phrase_ids.return_value = set()
        connector = MagicMock()
        connector.is_available.return_value = True
        connector.get_model_field_names.return_value = _EveryField()
        connector.add_notes.return_value = [12345]
        sources = [
            Source(id=1, status=SourceStatus.DONE, collection_id=5),
            Source(id=2, status=SourceStatus.DONE),
        ]
        use_case = SyncToAnkiUseCase(
            export_queue=ExportQueue(
                cards.words, anki_sync_repo, cards,
            ),
            anki_connector=connector,
            settings_repo=MagicMock(get=MagicMock(return_value=None)),
            anki_sync_repo=anki_sync_repo,
            template_renderer=MagicMock(
                render_recognition=MagicMock(return_value=NoteTemplates("F", "B", "")),
            ),
            anki_note_repo=MagicMock(),
            known_from_anki=MagicMock(**{"run.return_value": 0}),
            cloze_builder=ClozeBuilder(),
            scope_resolver=SourceScopeResolver(
                InMemorySourceRepository(sources),
                InMemoryCollectionRepository([Collection(id=5, name="IELTS")]),
            ),
        )

        result = use_case.execute_scope(SourceScope.collection(5), ExportGroup.READY)

        pushed = [c.kwargs["notes"][0]["Target"] for c in connector.add_notes.call_args_list]
        assert result.total == 1
        assert pushed == ["burnout"]


@pytest.mark.unit
class TestSyncChecksProgressInAnki:
    """Every export checks maturity first, also when nothing is new."""

    def setup_method(self) -> None:
        self.cards = ExportCards()
        self.cards.put([])
        self.anki_connector = MagicMock()
        self.anki_connector.is_available.return_value = True
        self.anki_connector.get_model_field_names.return_value = _EveryField()
        self.anki_connector.add_notes.return_value = [12345]
        settings_repo = MagicMock()
        settings_repo.get.return_value = None
        anki_sync_repo = MagicMock()
        anki_sync_repo.get_synced_phrase_ids.return_value = set()
        renderer = MagicMock()
        renderer.render_recognition.return_value = NoteTemplates("F", "B", "")
        self.anki_note_repo = MagicMock()
        self.known_from_anki = MagicMock()
        self.known_from_anki.run.return_value = 3
        self.use_case = SyncToAnkiUseCase(
            export_queue=ExportQueue(
                self.cards.words, anki_sync_repo, self.cards,
            ),
            anki_connector=self.anki_connector,
            settings_repo=settings_repo,
            anki_sync_repo=anki_sync_repo,
            template_renderer=renderer,
            anki_note_repo=self.anki_note_repo,
            known_from_anki=self.known_from_anki,
            cloze_builder=ClozeBuilder(),
            scope_resolver=empty_scope_resolver(),
        )

    def test_an_export_with_nothing_new_still_checks_progress(self) -> None:
        result = self.use_case.execute(source_id=1, group=ExportGroup.READY)

        assert result.total == 0
        assert result.matured == 3
        self.known_from_anki.run.assert_called_once()

    def test_anki_offline_with_nothing_new_is_no_error(self) -> None:
        self.anki_connector.is_available.return_value = False

        result = self.use_case.execute(source_id=1, group=ExportGroup.READY)

        assert result.total == 0
        assert result.matured == 0
        self.known_from_anki.run.assert_not_called()

    def test_anki_offline_with_new_cards_is_an_error(self) -> None:
        self.anki_connector.is_available.return_value = False
        self.cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN),
        ])

        with pytest.raises(AnkiNotAvailableError):
            self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

    def test_anki_failing_during_the_check_does_not_stop_the_export(self) -> None:
        self.known_from_anki.run.side_effect = AnkiNotAvailableError()
        self.cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN),
        ])

        result = self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        assert result.added == 1
        assert result.matured == 0

    def test_anki_failing_during_the_check_of_an_empty_export_is_no_error(self) -> None:
        self.known_from_anki.run.side_effect = AnkiNotAvailableError()

        result = self.use_case.execute(source_id=1, group=ExportGroup.READY)

        assert result.total == 0
        assert result.matured == 0

    def test_an_exported_word_is_learning_not_known(self) -> None:
        self.cards.put([
            _make_candidate(1, "burnout", WordStatus.LEARN),
        ])

        result = self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        assert result.added == 1
        assert result.matured == 3
        self.anki_note_repo.add.assert_called_once_with(12345, "burnout", "NOUN")
        self.known_from_anki.run.assert_called_once()
