from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.application.utils.anki_note_builders import CLOZE_FIELDS, CLOZE_NOTE_TYPE
from backend.application.utils.export_queue import ExportQueue
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.export_group import ExportGroup

pytestmark = pytest.mark.unit

GIVE_UP = "She finally gave up smoking last year."


def _cloze(
    candidate_id: int, indices: tuple[int, ...] = (3,), phrase: str = GIVE_UP
) -> CandidateCloze:
    return CandidateCloze(
        candidate_id=candidate_id,
        hidden_word_indices=indices,
        hint_kind=ClozeHintKind.TRANSLATION,
        custom_hint=None,
        phrase=phrase,
    )


def _candidate(
    candidate_id: int,
    lemma: str,
    phrase: str,
    surface: str | None = None,
    cloze: CandidateCloze | None = None,
) -> StoredCandidate:
    return StoredCandidate(
        id=candidate_id,
        source_id=1,
        lemma=lemma,
        pos="VERB",
        cefr_level="B2",
        zipf_frequency=4.0,
        context_fragment=phrase,
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.LEARN,
        surface_form=surface,
        meaning=CandidateMeaning(
            candidate_id=candidate_id,
            meaning="To stop doing something.",
            translation="бросить",
            synonyms="quit",
            examples=None,
            ipa="/ɡɪv ʌp/",
            generated_at=None,
        ),
        cloze=cloze,
    )


def _give_up(cloze: CandidateCloze | None) -> StoredCandidate:
    return _candidate(1, "give up", GIVE_UP, surface="gave up", cloze=cloze)


def _burnout() -> StoredCandidate:
    return _candidate(2, "burnout", "Burnout is real.")


class TestSyncToAnkiCloze:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.connector = MagicMock()
        self.connector.is_available.return_value = True
        self.connector.add_notes.return_value = [111]
        self.settings_repo = MagicMock()
        self.settings_repo.get.return_value = None
        self.anki_sync_repo = MagicMock()
        self.anki_sync_repo.get_synced_candidate_ids.return_value = set()
        self.renderer = MagicMock()
        self.renderer.render_all.return_value = {"front": "F", "back": "B", "css": "C"}
        self.renderer.render_cloze.return_value = {"front": "CF", "back": "CB", "css": "C"}
        self.use_case = SyncToAnkiUseCase(
            export_queue=ExportQueue(self.candidate_repo, self.anki_sync_repo),
            anki_connector=self.connector,
            settings_repo=self.settings_repo,
            anki_sync_repo=self.anki_sync_repo,
            template_renderer=self.renderer,
            known_word_repo=MagicMock(),
            cloze_builder=ClozeBuilder(),
        )

    def _sync(self, *candidates: StoredCandidate) -> None:
        self.candidate_repo.get_by_source.return_value = list(candidates)
        self.use_case.execute(source_id=1, group=ExportGroup.INCOMPLETE)

    def _added(self) -> list[tuple[str, dict[str, str]]]:
        return [
            (c.kwargs["model_name"], c.kwargs["notes"][0])
            for c in self.connector.add_notes.call_args_list
        ]

    def _ensured_models(self) -> list[str]:
        return [c.args[0] for c in self.connector.ensure_note_type.call_args_list]

    def test_cloze_candidate_goes_to_cloze_model(self) -> None:
        self._sync(_give_up(_cloze(1)))

        [(model, note)] = self._added()
        assert model == CLOZE_NOTE_TYPE == "AnythingToAnkiCloze"
        assert note["Text"] == "She finally gave {{c1::up}} smoking last year."
        assert note["Hint"] == "бросить"
        assert note["Target"] == "give up"
        assert note["IPA"] == "/ɡɪv ʌp/"
        assert note["Translation"] == "бросить"

    def test_cloze_model_created_with_is_cloze(self) -> None:
        self._sync(_give_up(_cloze(1)))

        self.connector.ensure_note_type.assert_called_once_with(
            "AnythingToAnkiCloze",
            list(CLOZE_FIELDS),
            front_template="CF",
            back_template="CB",
            css="C",
            is_cloze=True,
        )

    def test_mixed_batch_uses_both_models(self) -> None:
        self._sync(_burnout(), _give_up(_cloze(1)))

        assert self._ensured_models() == ["AnythingToAnkiType", "AnythingToAnkiCloze"]
        assert [model for model, _ in self._added()] == [
            "AnythingToAnkiType",
            "AnythingToAnkiCloze",
        ]

    def test_only_recognition_batch_does_not_touch_cloze_model(self) -> None:
        self._sync(_burnout(), _give_up(None))

        assert self._ensured_models() == ["AnythingToAnkiType"]
        assert {model for model, _ in self._added()} == {"AnythingToAnkiType"}
        self.renderer.render_cloze.assert_not_called()

    def test_cloze_duplicate_is_found_by_cloze_model(self) -> None:
        self.connector.add_notes.return_value = [None]
        self.connector.find_notes_by_target.return_value = [555]

        self._sync(_give_up(_cloze(1)))

        self.connector.find_notes_by_target.assert_called_once_with(
            "Default", "AnythingToAnkiCloze", "Target", "give up"
        )
        self.anki_sync_repo.mark_synced.assert_called_once_with(1, 555)

    def test_recognition_duplicate_is_found_by_its_model_and_target_field(self) -> None:
        self.connector.add_notes.return_value = [None]
        self.connector.find_notes_by_target.return_value = [555]

        self._sync(_burnout())

        self.connector.find_notes_by_target.assert_called_once_with(
            "Default", "AnythingToAnkiType", "Target", "burnout"
        )

    def test_stale_cloze_exported_with_rebuilt_gap(self) -> None:
        self._sync(_give_up(_cloze(1, indices=(0,), phrase="An old phrase.")))

        [(model, note)] = self._added()
        assert model == "AnythingToAnkiCloze"
        assert note["Text"] == "She finally {{c1::gave up}} smoking last year."

    def test_unavailable_hint_is_not_exported(self) -> None:
        cloze = replace(_cloze(1, indices=(2, 3)), hint_kind=ClozeHintKind.SYNONYMS)
        candidate = _give_up(cloze)
        assert candidate.meaning is not None
        leaking = replace(candidate.meaning, synonyms="give up, quit")
        candidate = replace(candidate, meaning=leaking)
        self._sync(candidate)

        [(_, note)] = self._added()
        assert note["Hint"] == ""
