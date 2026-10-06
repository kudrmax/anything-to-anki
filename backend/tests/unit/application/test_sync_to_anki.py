from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.application.utils.anki_template_renderer import NoteTemplates
from backend.application.utils.export_queue import ExportQueue
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import AnkiNotAvailableError
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.export_group import ExportGroup


def _make_candidate(
    candidate_id: int,
    lemma: str,
    status: CandidateStatus,
    meaning: str | None = None,
    ipa: str | None = None,
    translation: str | None = None,
    synonyms: str | None = None,
    examples: str | None = None,
    source_id: int = 1,
    tts_path: str | None = "/tmp/tts.mp3",
) -> StoredCandidate:
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
    return StoredCandidate(
        id=candidate_id,
        source_id=source_id,
        lemma=lemma,
        pos="NOUN",
        cefr_level="B2",
        zipf_frequency=3.5,
        context_fragment=f"context with {lemma} here",
        fragment_purity="clean",
        occurrences=1,
        status=status,
        meaning=meaning_obj,
        media=None,
        tts=CandidateTTS(candidate_id=candidate_id, audio_path=tts_path, generated_at=None),
    )


@pytest.mark.unit
class TestSyncToAnkiUseCase:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.anki_connector = MagicMock()
        self.settings_repo = MagicMock()
        self.anki_sync_repo = MagicMock()
        self.template_renderer = MagicMock()
        self.known_word_repo = MagicMock()
        self.template_renderer.render_recognition.return_value = NoteTemplates(
            "<front/>", "<back/>", "",
        )
        self.settings_repo.get.return_value = None  # use default deck
        self.anki_sync_repo.get_synced_candidate_ids.return_value = set()
        self.use_case = SyncToAnkiUseCase(
            export_queue=ExportQueue(self.candidate_repo, self.anki_sync_repo),
            anki_connector=self.anki_connector,
            settings_repo=self.settings_repo,
            anki_sync_repo=self.anki_sync_repo,
            template_renderer=self.template_renderer,
            known_word_repo=self.known_word_repo,
            cloze_builder=ClozeBuilder(),
        )

    def test_returns_zero_when_no_learn_candidates(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "word", CandidateStatus.SKIP),
        ]
        result = self.use_case.execute(source_id=1, group=ExportGroup.READY)
        assert result.total == 0
        assert result.added == 0
        self.anki_connector.is_available.assert_not_called()

    def test_raises_when_anki_unavailable(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "word", CandidateStatus.LEARN),
        ]
        self.anki_connector.is_available.return_value = False
        with pytest.raises(AnkiNotAvailableError):
            self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

    def test_adds_new_cards(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "burnout", CandidateStatus.LEARN, meaning="выгорание"),
            _make_candidate(2, "relentless", CandidateStatus.LEARN, meaning="неумолимый"),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        result = self.use_case.execute(source_id=1, group=ExportGroup.READY)

        assert result.total == 2
        assert result.added == 2
        assert result.skipped == 0
        assert result.errors == 0
        assert self.known_word_repo.add.call_count == 2
        self.known_word_repo.add.assert_any_call("burnout", "NOUN")
        self.known_word_repo.add.assert_any_call("relentless", "NOUN")

    def test_exports_only_not_yet_exported_candidates(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "burnout", CandidateStatus.LEARN),
            _make_candidate(2, "relentless", CandidateStatus.LEARN),
        ]
        self.anki_sync_repo.get_synced_candidate_ids.return_value = {1}  # burnout already exported
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
        self.known_word_repo.add.assert_called_once_with("relentless", "NOUN")

    def test_all_already_exported_returns_without_calling_anki(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "burnout", CandidateStatus.LEARN),
        ]
        self.anki_sync_repo.get_synced_candidate_ids.return_value = {1}

        result = self.use_case.execute(source_id=1, group=ExportGroup.READY)

        assert result.total == 0
        assert result.added == 0
        assert result.skipped == 0
        self.anki_connector.is_available.assert_not_called()
        self.anki_connector.add_notes.assert_not_called()
        self.known_word_repo.add.assert_not_called()

    def test_marks_synced_after_successful_add(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "burnout", CandidateStatus.LEARN),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        self.anki_sync_repo.mark_synced.assert_called_once_with(1, 12345)
        self.known_word_repo.add.assert_called_once_with("burnout", "NOUN")

    def test_counts_as_skipped_when_note_already_exists_in_anki(self) -> None:
        # add_notes returns None (allowDuplicate=False), but note exists in Anki
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "burnout", CandidateStatus.LEARN),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [None]
        self.anki_connector.find_notes_by_target.return_value = [99999]

        result = self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        assert result.added == 0
        assert result.skipped == 1
        assert result.skipped_lemmas == ["burnout"]
        assert result.errors == 0
        self.anki_sync_repo.mark_synced.assert_called_once_with(1, 99999)
        self.known_word_repo.add.assert_called_once_with("burnout", "NOUN")

    def test_counts_errors_when_add_fails_and_note_not_found(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "burnout", CandidateStatus.LEARN),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [None]
        self.anki_connector.find_notes_by_target.return_value = []

        result = self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        assert result.added == 0
        assert result.errors == 1
        assert result.error_lemmas == ["burnout"]
        self.anki_sync_repo.mark_synced.assert_not_called()
        self.known_word_repo.add.assert_not_called()

    def test_duplicate_exception_marks_synced_and_counts_as_skipped(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "burnout", CandidateStatus.LEARN),
        ]
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
        self.anki_sync_repo.mark_synced.assert_called_once_with(1, 99999)
        self.known_word_repo.add.assert_called_once_with("burnout", "NOUN")

    def test_counts_errors_on_exception(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "burnout", CandidateStatus.LEARN),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.side_effect = RuntimeError("some unexpected error")

        result = self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        assert result.added == 0
        assert result.errors == 1
        assert result.error_lemmas == ["burnout"]
        self.anki_sync_repo.mark_synced.assert_not_called()
        self.known_word_repo.add.assert_not_called()

    def test_meaning_from_candidate(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "thug", CandidateStatus.LEARN, meaning="бандит, головорез"),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.READY)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert note[0]["Meaning"] == "бандит, головорез"

    def test_no_meaning_becomes_empty_string(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "thug", CandidateStatus.LEARN, meaning=None),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert note[0]["Meaning"] == ""

    def test_ipa_from_candidate(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "thug", CandidateStatus.LEARN, ipa="/θʌɡ/"),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert note[0]["IPA"] == "/θʌɡ/"

    def test_image_field_populated_when_media_present(self) -> None:
        candidate = _make_candidate(1, "thug", CandidateStatus.LEARN, meaning="бандит")
        candidate = StoredCandidate(
            id=candidate.id,
            source_id=candidate.source_id,
            lemma=candidate.lemma,
            pos=candidate.pos,
            cefr_level=candidate.cefr_level,
            zipf_frequency=candidate.zipf_frequency,
            context_fragment=candidate.context_fragment,
            fragment_purity=candidate.fragment_purity,
            occurrences=candidate.occurrences,
            status=candidate.status,
            meaning=candidate.meaning,
            media=CandidateMedia(
                candidate_id=1,
                screenshot_path="/tmp/img.png",
                audio_path="/tmp/snd.mp3",
                start_ms=0,
                end_ms=1000,
                generated_at=datetime(2026, 4, 8, tzinfo=UTC),
            ),
        )
        self.candidate_repo.get_by_source.return_value = [candidate]
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
        candidate = _make_candidate(1, "drain", CandidateStatus.LEARN, meaning="слив")
        candidate.media = CandidateMedia(
            candidate_id=1, screenshot_path="/tmp/1_screenshot.webp", audio_path=None,
            start_ms=0, end_ms=1000, generated_at=None,
        )
        candidate.meaning_image = CandidateMeaningImage(
            candidate_id=1, image_path="/tmp/1_meaning.0a1b2c3d4e.webp",
        )
        self.candidate_repo.get_by_source.return_value = [candidate]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        exists_path = "backend.application.utils.anki_note_builders.os.path.exists"
        with patch(exists_path, return_value=True):
            self.use_case.execute(source_id=1, group=ExportGroup.READY)

        note = self.anki_connector.add_notes.call_args.kwargs["notes"][0]
        assert note["Image"] == '<img src="1_screenshot.webp">'
        assert note["MeaningImage"] == '<img src="1_meaning.0a1b2c3d4e.webp">'

    def test_meaning_image_without_a_frame_leaves_the_front_picture_empty(self) -> None:
        candidate = _make_candidate(1, "drain", CandidateStatus.LEARN, meaning="слив")
        candidate.meaning_image = CandidateMeaningImage(
            candidate_id=1, image_path="/tmp/1_meaning.0a1b2c3d4e.webp",
        )
        self.candidate_repo.get_by_source.return_value = [candidate]
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
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "thug", CandidateStatus.LEARN, meaning="бандит"),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.READY)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert "Image" not in note[0]
        assert "Audio" not in note[0]
        self.anki_connector.store_media_file.assert_not_called()

    def test_execute_all_aggregates_results(self) -> None:
        """execute_all iterates over sources with learn candidates and aggregates."""
        candidate1 = _make_candidate(10, "burnout", CandidateStatus.LEARN, source_id=1)
        candidate2 = _make_candidate(20, "pursuit", CandidateStatus.LEARN, source_id=2)

        self.candidate_repo.get_all_by_status.return_value = [candidate1, candidate2]
        self.candidate_repo.get_by_source.side_effect = lambda sid: {
            1: [candidate1],
            2: [candidate2],
        }[sid]
        self.anki_sync_repo.get_synced_candidate_ids.return_value = set()
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        result = self.use_case.execute_all(ExportGroup.INCOMPLETE)

        assert result.total == 2
        assert result.added == 2
        assert result.errors == 0

    def test_execute_all_skips_sources_with_everything_exported(self) -> None:
        exported = _make_candidate(10, "burnout", CandidateStatus.LEARN, source_id=1)
        fresh = _make_candidate(20, "pursuit", CandidateStatus.LEARN, source_id=2)

        self.candidate_repo.get_all_by_status.return_value = [exported, fresh]
        self.candidate_repo.get_by_source.side_effect = lambda sid: {
            1: [exported],
            2: [fresh],
        }[sid]
        self.anki_sync_repo.get_synced_candidate_ids.side_effect = (
            lambda ids: {10} & set(ids)
        )
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        result = self.use_case.execute_all(ExportGroup.INCOMPLETE)

        assert result.total == 1
        assert result.added == 1
        self.candidate_repo.get_by_source.assert_called_once_with(2)

    def _added_note_calls(self) -> list[Any]:
        return list(self.anki_connector.add_notes.call_args_list)

    def test_exports_only_the_requested_group(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "ready", CandidateStatus.LEARN, meaning="done"),
            _make_candidate(2, "no_meaning", CandidateStatus.LEARN),
            _make_candidate(3, "no_audio", CandidateStatus.LEARN, meaning="done", tts_path=None),
        ]
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

    def test_execute_all_empty_when_no_learn(self) -> None:
        self.candidate_repo.get_all_by_status.return_value = []
        result = self.use_case.execute_all(ExportGroup.READY)
        assert result.total == 0
        assert result.added == 0

    def test_translation_and_synonyms_from_candidate(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                1, "thug", CandidateStatus.LEARN,
                meaning="бандит",
                translation="бандит",
                synonyms="ruffian, gangster",
            ),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.READY)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert note[0]["Translation"] == "бандит"
        assert note[0]["Synonyms"] == "ruffian, gangster"

    def test_translation_synonyms_omitted_for_legacy_records(self) -> None:
        # Legacy candidate has meaning but translation and synonyms are NULL
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "thug", CandidateStatus.LEARN, meaning="бандит"),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1, group=ExportGroup.READY)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert "Translation" not in note[0]
        assert "Synonyms" not in note[0]

    def test_examples_formatted_as_bullet_list(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                1, "aisle", CandidateStatus.LEARN,
                meaning="проход",
                examples=(
                    "The bride walked down the **aisle**.\n"
                    "All guests stood at the end of the **aisle**."
                ),
            ),
        ]
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
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(
                1, "thug", CandidateStatus.LEARN,
                meaning="бандит",
                translation="бандит\nголоворез",
                synonyms="ruffian\ngangster",
            ),
        ]
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
        candidate = StoredCandidate(
            id=1,
            source_id=1,
            lemma="thug",
            pos="NOUN",
            cefr_level="B2",
            zipf_frequency=3.5,
            context_fragment="context with thug here",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.LEARN,
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
        self.candidate_repo.get_by_source.return_value = [candidate]
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
