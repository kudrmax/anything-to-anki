from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.application.utils.anki_note_settings import AnkiFieldNames
from backend.application.utils.anki_template_renderer import NoteTemplates
from backend.application.utils.export_queue import ExportCard, ExportQueue
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.export_group import ExportGroup
from backend.domain.value_objects.phrase_origin_kind import DecisionKind
from backend.domain.value_objects.word_status import WordStatus

from tests.export_support import ExportCards, export_card, with_phrase
from tests.phrase_support import phrase
from tests.unit.application.scope_fakes import empty_scope_resolver
from tests.word_support import phrase_id_of

pytestmark = pytest.mark.unit

GIVE_UP = "She finally gave up smoking last year."


class _EveryField(list[str]):
    """Fields of a note type that has every field the export asks for."""

    def __contains__(self, name: object) -> bool:
        return True


def _cloze(
    candidate_id: int, indices: tuple[int, ...] = (3,), text: str = GIVE_UP
) -> CandidateCloze:
    return CandidateCloze(
        candidate_id=candidate_id,
        hidden_word_indices=indices,
        hint_kind=ClozeHintKind.TRANSLATION,
        custom_hint=None,
        phrase=text,
    )


def _candidate(
    candidate_id: int,
    lemma: str,
    text: str,
    surface: str | None = None,
    cloze: CandidateCloze | None = None,
    kind: DecisionKind | None = None,
) -> ExportCard:
    return export_card(
        StoredCandidate(
            id=candidate_id,
            source_id=1,
            lemma=lemma,
            pos="VERB",
            cefr_level="B2",
            zipf_frequency=4.0,
            occurrences=1,
            status=WordStatus.LEARN,
        ),
        phrase(text, surface or lemma),
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
        kind=kind,
    )


def _give_up(cloze: CandidateCloze | None, kind: DecisionKind | None = None) -> ExportCard:
    return _candidate(1, "give up", GIVE_UP, surface="gave up", cloze=cloze, kind=kind)


def _burnout() -> ExportCard:
    return _candidate(2, "burnout", "Burnout is real.")


class TestSyncToAnkiCloze:
    def setup_method(self) -> None:
        self.cards = ExportCards()
        self.connector = MagicMock()
        self.connector.is_available.return_value = True
        self.connector.add_notes.return_value = [111]
        self.connector.get_model_field_names.return_value = _EveryField()
        self.settings_repo = MagicMock()
        self.settings_repo.get.return_value = None
        self.anki_sync_repo = MagicMock()
        self.anki_sync_repo.get_synced_phrase_ids.return_value = set()
        self.renderer = MagicMock()
        self.renderer.render_recognition.return_value = NoteTemplates("F", "B", "C")
        self.renderer.render_cloze.return_value = NoteTemplates("CF", "CB", "C")
        self.use_case = SyncToAnkiUseCase(
            export_queue=ExportQueue(
                self.cards.words, self.anki_sync_repo, self.cards,  # type: ignore[arg-type]
            ),
            anki_connector=self.connector,
            settings_repo=self.settings_repo,
            anki_sync_repo=self.anki_sync_repo,
            template_renderer=self.renderer,
            anki_note_repo=MagicMock(),
            cloze_builder=ClozeBuilder(),
            scope_resolver=empty_scope_resolver(),
        )

    def _sync(self, *candidates: ExportCard) -> None:
        self.cards.put(list(candidates))
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
        assert model == "AnythingToAnkiCloze"
        assert note["Sentence"] == "She finally gave {{c1::up::бросить}} smoking last year."
        assert "Hint" not in note
        assert note["Target"] == "give up"
        assert note["IPA"] == "/ɡɪv ʌp/"
        assert note["Translation"] == "бросить"

    def test_the_note_type_follows_the_kind_of_the_decision(self) -> None:
        learn_with_markup = _give_up(_cloze(1), kind=DecisionKind.LEARN)

        self._sync(learn_with_markup)

        [(model, note)] = self._added()
        assert model == "AnythingToAnkiType"
        assert "{{c1::" not in note["Sentence"]

    def test_a_cloze_decided_without_markup_hides_the_target(self) -> None:
        bare = _give_up(None, kind=DecisionKind.CLOZE)

        self._sync(bare)

        [(model, note)] = self._added()
        assert model == "AnythingToAnkiCloze"
        assert note["Sentence"] == "She finally {{c1::gave up}} smoking last year."

    def test_cloze_model_created_with_is_cloze(self) -> None:
        self._sync(_give_up(_cloze(1)))

        self.connector.ensure_note_type.assert_called_once_with(
            "AnythingToAnkiCloze",
            AnkiFieldNames.read(self.settings_repo).cloze_fields(),
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
        self.anki_sync_repo.mark_synced.assert_called_once_with(1, 555, phrase_id_of(1))

    def test_recognition_duplicate_is_found_by_its_model_and_target_field(self) -> None:
        self.connector.add_notes.return_value = [None]
        self.connector.find_notes_by_target.return_value = [555]

        self._sync(_burnout())

        self.connector.find_notes_by_target.assert_called_once_with(
            "Default", "AnythingToAnkiType", "Target", "burnout"
        )

    def test_stale_cloze_exported_with_rebuilt_gap(self) -> None:
        self._sync(_give_up(_cloze(1, indices=(0,), text="An old phrase.")))

        [(model, note)] = self._added()
        assert model == "AnythingToAnkiCloze"
        assert note["Sentence"] == "She finally {{c1::gave up::бросить}} smoking last year."

    def test_unavailable_hint_is_not_exported(self) -> None:
        cloze = replace(_cloze(1, indices=(2, 3)), hint_kind=ClozeHintKind.SYNONYMS)
        candidate = _give_up(cloze)
        assert candidate.phrase.meaning is not None
        leaking = replace(candidate.phrase.meaning, synonyms="give up, quit")
        candidate = with_phrase(candidate, meaning=leaking)
        self._sync(candidate)

        [(_, note)] = self._added()
        assert note["Sentence"] == "She finally {{c1::gave up}} smoking last year."

    def test_cloze_goes_to_the_users_cloze_type_and_field_names(self) -> None:
        names = {"anki_cloze_note_type": "Main Cloze", "anki_field_sentence": "Phrase"}
        self.settings_repo.get.side_effect = lambda key, default=None: names.get(key)

        self._sync(_give_up(_cloze(1)))

        [(model, note)] = self._added()
        assert model == "Main Cloze"
        assert note["Phrase"] == "She finally gave {{c1::up::бросить}} smoking last year."
        assert self._ensured_models() == []
