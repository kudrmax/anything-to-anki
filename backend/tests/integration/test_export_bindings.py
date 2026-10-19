"""Export binds the card to its Anki note (S1), in a real database: the timer starts at
that export, a note is reused, and a switch of kind makes a note of the other kind."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.application.utils.anki_template_renderer import NoteTemplates
from backend.application.utils.export_queue import ExportQueue
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.card_choice import Press
from backend.domain.value_objects.export_group import ExportGroup
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import text

from tests.decision_support import NOW, Decisions
from tests.integration.conftest import insert_source
from tests.unit.application.scope_fakes import empty_scope_resolver
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

WORD = 1
CARD = phrase_id_of(WORD)
OTHER_SOURCE = 2
OTHER_WORD = 50
OTHER_CARD = phrase_id_of(OTHER_WORD)
LEMMA = "glare"
NOTE = 111
CLOZE_NOTE = 222
SOURCE = 1


class _EveryField(list[str]):
    def __contains__(self, name: object) -> bool:
        return True


class Bench:
    def __init__(self, session: Session) -> None:
        self.session = session
        insert_word(session, WORD, lemma=LEMMA, pos="VERB", phrase_text="He glared at me.")
        self._ready(CARD, WORD)
        self.decisions = Decisions(session)
        self.connector = MagicMock()
        self.connector.is_available.return_value = True
        self.connector.get_model_field_names.return_value = _EveryField()
        self.connector.add_notes.return_value = [NOTE]
        self.connector.find_notes_by_target.return_value = []

    def _ready(self, phrase_id: int, word_id: int) -> None:
        """A meaning and audio: the card is ready to export."""
        SqlaCandidateMeaningRepository(self.session).upsert_for_phrase(
            phrase_id, CandidateMeaning(
                candidate_id=word_id, meaning="to look angrily", translation=None,
                synonyms=None, examples=None, ipa=None, generated_at=None,
            ),
        )
        SqlaCandidateTTSRepository(self.session).upsert_for_phrase(
            phrase_id, CandidateTTS(
                candidate_id=word_id, audio_path="/media/1/tts.mp3", generated_at=None,
            ),
        )

    def other_source(self) -> None:
        insert_source(self.session, OTHER_SOURCE)
        insert_word(self.session, OTHER_WORD, source_id=OTHER_SOURCE, lemma=LEMMA, pos="VERB",
                    phrase_text="She glared back.")
        self._ready(OTHER_CARD, OTHER_WORD)

    def later(self, days: int) -> None:
        self.decisions = self.decisions.request(NOW + timedelta(days=days))

    def press(self, phrase_id: int, button: Press) -> None:
        self.decisions.decide_phrase().press(phrase_id, button)

    def queue(self) -> ExportQueue:
        return ExportQueue(
            SqlaCandidateRepository(self.session), SqlaOccurrenceRepository(self.session),
            self.decisions.word_states, self.decisions.vocabulary,
        )

    def export(self, source_id: int = SOURCE, group: ExportGroup = ExportGroup.READY) -> None:
        settings = MagicMock()
        settings.get.return_value = None
        renderer = MagicMock()
        renderer.render_recognition.return_value = NoteTemplates("F", "B", "")
        renderer.render_cloze.return_value = NoteTemplates("CF", "CB", "")
        SyncToAnkiUseCase(
            export_queue=self.queue(),
            anki_connector=self.connector,
            settings_repo=settings,
            template_renderer=renderer,
            cloze_builder=ClozeBuilder(),
            scope_resolver=empty_scope_resolver(),
            vocabulary=self.decisions.vocabulary,
            effects=self.decisions.effects(),
        ).execute(source_id, group)

    def status(self, word_id: int = WORD) -> str:
        return str(self.session.execute(
            text("SELECT status FROM candidates WHERE id = :id"), {"id": word_id},
        ).scalar_one())

    def rows(self) -> list[tuple[object, ...]]:
        """(phrase, note, kind, learning_since, active) of every binding, in order."""
        return [
            tuple(row) for row in self.session.execute(text(
                "SELECT phrase_id, anki_note_id, note_kind, learning_since,"
                " released_at IS NULL FROM anki_synced_cards ORDER BY id"
            ))
        ]


def _stored(moment: datetime) -> str:
    return moment.replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds")


@pytest.fixture
def bench(db_session: Session, source_id: int) -> Bench:
    del source_id
    return Bench(db_session)


def test_export_makes_the_word_learning_and_starts_its_timer_now(bench: Bench) -> None:
    bench.press(CARD, Press.LEARN)

    bench.export()

    assert bench.status() == "learning"
    assert bench.rows() == [(CARD, NOTE, "learn", _stored(NOW), 1)]
    lemma = bench.session.execute(text("SELECT lemma, pos FROM anki_synced_cards")).one()
    assert tuple(lemma) == (LEMMA, "VERB")
    assert bench.queue().for_source(SOURCE).pending == []


def test_re_export_after_a_removal_binds_the_same_note_with_a_new_timer(bench: Bench) -> None:
    bench.press(CARD, Press.LEARN)
    bench.export()
    bench.later(days=5)
    bench.press(CARD, Press.LEARN)              # P17: the word is new, the note stays in Anki
    assert bench.status() == "pending"
    bench.press(CARD, Press.LEARN)
    bench.connector.add_notes.return_value = [None]       # Anki has the note: a duplicate
    bench.connector.find_notes_by_target.return_value = [NOTE]

    bench.export()

    assert bench.status() == "learning"
    assert bench.rows() == [
        (CARD, NOTE, "learn", _stored(NOW), 0),
        (CARD, NOTE, "learn", _stored(NOW + timedelta(days=5)), 1),
    ]


def test_switching_kind_in_anki_exports_a_note_of_the_other_kind(bench: Bench) -> None:
    bench.press(CARD, Press.LEARN)
    bench.export()
    bench.press(CARD, Press.CLOZE)              # P18: released, back in the queue
    assert bench.status() == "learn"
    bench.connector.add_notes.return_value = [CLOZE_NOTE]

    bench.export(group=ExportGroup.INCOMPLETE)  # a cloze without markup is incomplete

    assert bench.rows() == [
        (CARD, NOTE, "learn", _stored(NOW), 0),
        (CARD, CLOZE_NOTE, "cloze", _stored(NOW), 1),
    ]
    models = [c.kwargs["model_name"] for c in bench.connector.add_notes.call_args_list]
    assert models[0] != models[1]


def test_two_sources_bind_one_note(bench: Bench) -> None:
    """Source 1's card went back to new; source 2 learns the lemma and its export finds
    the same note in Anki."""
    bench.other_source()
    bench.press(CARD, Press.LEARN)
    bench.export()
    bench.press(CARD, Press.LEARN)
    bench.press(OTHER_CARD, Press.LEARN)
    bench.connector.add_notes.return_value = [None]
    bench.connector.find_notes_by_target.return_value = [NOTE]

    bench.export(OTHER_SOURCE)

    assert [(phrase, note, active) for phrase, note, _, _, active in bench.rows()] == [
        (CARD, NOTE, 0), (OTHER_CARD, NOTE, 1),
    ]
    assert bench.status(OTHER_WORD) == "learning"


def test_a_cloze_without_markup_is_incomplete(bench: Bench) -> None:
    bench.press(CARD, Press.CLOZE)

    batch = bench.queue().for_source(SOURCE)

    assert batch.in_group(ExportGroup.READY) == []
    [card] = batch.in_group(ExportGroup.INCOMPLETE)
    assert card.is_cloze


def test_a_learn_put_in_known_after_it_leaves_the_queue(bench: Bench) -> None:
    """Q15: the later action wins."""
    bench.press(CARD, Press.LEARN)
    bench.session.execute(text(
        "INSERT INTO known_words (lemma, pos, created_at) VALUES ('glare', 'VERB', '2026-01-01')"
    ))
    bench.later(days=0)

    bench.export()

    assert bench.queue().for_source(SOURCE).pending == []
    bench.connector.add_notes.assert_not_called()
    assert bench.rows() == []


def test_the_queue_reads_only_the_words_chosen_to_learn(bench: Bench) -> None:
    """A source's other words stay unread: the queue loads its words by id."""
    bench.other_source()
    bench.press(OTHER_CARD, Press.SKIP)
    bench.press(CARD, Press.LEARN)
    states = bench.decisions.word_states
    read_by_source = MagicMock(side_effect=AssertionError("the queue reads words by id"))
    with patch.object(states, "of_source", read_by_source):
        batch = bench.queue().for_all()

    assert [card.word_id for card in batch.pending] == [WORD]


def test_the_pending_count_is_the_queue_length(bench: Bench) -> None:
    assert bench.queue().pending_count() == len(bench.queue().for_all().pending) == 0
    bench.press(CARD, Press.LEARN)
    assert bench.queue().pending_count() == len(bench.queue().for_all().pending) == 1

    bench.export()

    assert bench.queue().pending_count() == len(bench.queue().for_all().pending) == 0
