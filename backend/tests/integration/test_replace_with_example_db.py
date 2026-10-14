"""Replace with example: a new `example` phrase of the word takes the card's place."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.replace_with_example import ReplaceWithExampleUseCase
from backend.application.utils.export_queue import ExportQueue
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.occurrence import Occurrence
from backend.domain.exceptions import (
    AlreadyInAnkiError,
    PhraseNotFoundError,
    TargetNotInPhraseError,
)
from backend.domain.services.export_readiness import missing_parts
from backend.domain.services.phrase_building import target_by_lemma
from backend.domain.value_objects.export_group import ExportGroup
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin_kind import (
    DecisionKind,
    OccurrenceOrigin,
    ShownBy,
)
from backend.infrastructure.persistence.models import PhraseWordModel
from backend.infrastructure.persistence.sqla_anki_sync_repository import SqlaAnkiSyncRepository
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import select, text

from tests.phrase_support import phrase
from tests.word_support import insert_word

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

WORD = 1
CARD = 1
_LEMMAS = {"ran": "run", "runs": "run"}


def _read_for(text: str, lemma: str) -> Phrase:
    found = phrase(text, lemma, lemmas=_LEMMAS)
    if not target_by_lemma(found.words, text, lemma):
        raise TargetNotInPhraseError()
    return found


def _read(text: str, spans: list[tuple[int, int]]) -> Phrase:
    whole = phrase(text, lemmas=_LEMMAS)
    target = tuple(
        i for i, word in enumerate(whole.words)
        if any(word.start < end and start < word.end for start, end in spans)
    )
    if not target:
        raise TargetNotInPhraseError()
    return whole.with_target(target)


class Bench:
    """Word `run` of source 1 whose selection card is phrase CARD."""

    def __init__(self, session: Session) -> None:
        self.session = session
        insert_word(session, WORD, lemma="run", pos="VERB", phrase_text="He ran to the store.")
        self.occurrences = SqlaOccurrenceRepository(session)
        self.review_status = MagicMock()
        reader = MagicMock()
        reader.read_for.side_effect = _read_for
        reader.read.side_effect = _read
        self.use_case = ReplaceWithExampleUseCase(
            occurrence_repo=self.occurrences,
            candidate_repo=SqlaCandidateRepository(session),
            review_status=self.review_status,
            phrase_reader=reader,
            job_repo=SqlaJobRepository(session),
        )

    def replace(self, phrase_id: int, example: str = "She runs every morning.") -> Occurrence:
        """The example made, the newest phrase of the word."""
        self.use_case.execute(phrase_id, example)
        made = self.occurrences.of_word(WORD)[-1]
        assert made.origin is OccurrenceOrigin.EXAMPLE
        return made

    def get(self, phrase_id: int) -> Occurrence:
        found = self.occurrences.get(phrase_id)
        assert found is not None
        return found

    def decide(self, phrase_id: int, kind: DecisionKind) -> None:
        self.session.execute(text("UPDATE candidates SET status = 'learn' WHERE id = :id"),
                             {"id": WORD})
        self.occurrences.set_decision(WORD, phrase_id, kind)

    def give_meaning_and_audio(self, phrase_id: int) -> None:
        SqlaCandidateMeaningRepository(self.session).upsert_for_phrase(phrase_id, CandidateMeaning(
            candidate_id=WORD, meaning="to move fast", translation=None, synonyms=None,
            examples=None, ipa=None, generated_at=None,
        ))
        SqlaCandidateTTSRepository(self.session).upsert_for_phrase(phrase_id, CandidateTTS(
            candidate_id=WORD, audio_path="/media/1/tts.mp3", generated_at=None,
        ))

    def export_queue(self) -> ExportQueue:
        return ExportQueue(
            SqlaCandidateRepository(self.session), SqlaAnkiSyncRepository(self.session),
            self.occurrences,
        )

    def add_manual(self) -> int:
        added = self.occurrences.add(Occurrence(
            candidate_id=WORD, origin=OccurrenceOrigin.MANUAL,
            source_phrase=phrase("We ran home.", "ran", lemmas=_LEMMAS), phrase_position=None,
            key=None, fragment_score=None, shown_by=ShownBy.USER,
        ))
        assert added.id is not None
        return added.id


@pytest.fixture
def bench(db_session: Session, source_id: int) -> Bench:
    del source_id
    return Bench(db_session)


def test_the_example_is_a_new_phrase_of_the_word_shown_instead_of_the_card(bench: Bench) -> None:
    example = bench.replace(CARD)

    assert example.candidate_id == WORD
    assert example.shown_by is ShownBy.USER
    assert example.source_phrase.text == "She runs every morning."
    assert example.source_phrase.target_text() == "runs"
    assert example.phrase_position is None
    replaced = bench.get(CARD)
    assert replaced.shown_by is None
    assert not replaced.skipped
    bench.review_status.refresh.assert_called_once_with(1)


def test_the_answer_is_the_word_seen_through_the_example(bench: Bench) -> None:
    result = bench.use_case.execute(CARD, "She runs every morning.")

    assert result.id == WORD
    assert result.phrase.text == "She runs every morning."
    assert result.phrase_id != CARD


def test_the_answer_is_the_example_card_when_the_word_shows_another_phrase(
    bench: Bench,
) -> None:
    """The ✨ that follows the replacement must reach the example, not the word's other card."""
    bench.add_manual()

    result = bench.use_case.execute(CARD, "She runs every morning.")

    example = bench.occurrences.of_word(WORD)[-1]
    assert result.phrase_id == example.id
    assert result.phrase.text == "She runs every morning."
    assert result.meaning is None


def test_the_example_gets_its_meaning_queued(bench: Bench) -> None:
    example = bench.replace(CARD)

    jobs = SqlaJobRepository(bench.session).get_jobs_by_status([JobStatus.QUEUED])
    assert [(j.job_type, j.candidate_id, j.phrase_id, j.phrase_revision) for j in jobs] == [
        (JobType.MEANING, WORD, example.id, example.revision),
    ]


def test_bold_words_are_the_target_and_the_markup_goes(bench: Bench) -> None:
    example = bench.replace(CARD, "Run fast, she **runs** every morning.")

    assert example.source_phrase.text == "Run fast, she runs every morning."
    assert example.source_phrase.target == (3,)


def test_an_example_without_the_target_is_refused(bench: Bench) -> None:
    with pytest.raises(TargetNotInPhraseError):
        bench.use_case.execute(CARD, "She walks every morning.")

    assert len(bench.occurrences.of_word(WORD)) == 1
    assert bench.get(CARD).shown_by is ShownBy.SELECTION


@pytest.mark.parametrize("example", ["", "   "])
def test_an_empty_example_is_refused(bench: Bench, example: str) -> None:
    with pytest.raises(ValueError, match="example_text"):
        bench.use_case.execute(CARD, example)


def test_an_unknown_phrase_is_not_found(bench: Bench) -> None:
    with pytest.raises(PhraseNotFoundError):
        bench.use_case.execute(999, "She runs every morning.")


def test_the_example_words_are_the_phrase_words(bench: Bench) -> None:
    example = bench.replace(CARD)

    lemmas = set(bench.session.scalars(
        select(PhraseWordModel.lemma).where(PhraseWordModel.phrase_id == example.id)
    ))
    assert lemmas == {"she", "run", "every", "morning"}


# ── the decision moves with its kind ──────────────────────────────────


@pytest.mark.parametrize("kind", [DecisionKind.LEARN, DecisionKind.CLOZE])
def test_the_decision_moves_to_the_example_with_its_kind(bench: Bench, kind: DecisionKind) -> None:
    bench.decide(CARD, kind)

    example = bench.replace(CARD)

    assert example.is_decision
    assert example.decision_kind is kind
    assert not bench.get(CARD).is_decision


def test_an_exported_decision_card_cannot_be_replaced(bench: Bench) -> None:
    bench.decide(CARD, DecisionKind.LEARN)
    SqlaAnkiSyncRepository(bench.session).mark_synced(WORD, 900, CARD)

    with pytest.raises(AlreadyInAnkiError):
        bench.use_case.execute(CARD, "She runs every morning.")

    assert len(bench.occurrences.of_word(WORD)) == 1
    assert bench.get(CARD).is_decision
    assert bench.get(CARD).shown_by is ShownBy.SELECTION


# ── which card the example replaced ───────────────────────────────────


def test_an_example_in_place_of_the_selection_card_replaces_the_selection(bench: Bench) -> None:
    example = bench.replace(CARD)

    assert example.replaces_selection


def test_an_example_in_place_of_a_manual_card_does_not(bench: Bench) -> None:
    manual = bench.add_manual()

    example = bench.replace(manual)

    assert not example.replaces_selection
    assert bench.get(CARD).shown_by is ShownBy.SELECTION


def test_an_example_in_place_of_an_example_of_the_selection_card_keeps_replacing_it(
    bench: Bench,
) -> None:
    first = bench.replace(CARD)
    assert first.id is not None

    second = bench.replace(first.id, "They ran away.")

    assert second.replaces_selection


@pytest.mark.parametrize(
    ("kind", "missing"),
    [
        (DecisionKind.LEARN, ["meaning", "audio"]),
        (DecisionKind.CLOZE, ["meaning", "audio", "cloze"]),
    ],
)
def test_export_takes_the_example_and_holds_it_back_until_generated(
    bench: Bench, kind: DecisionKind, missing: list[str],
) -> None:
    bench.decide(CARD, kind)
    bench.give_meaning_and_audio(CARD)
    example = bench.replace(CARD)

    batch = bench.export_queue().for_source(1)

    [card] = batch.pending
    assert card.phrase.id == example.id
    assert batch.in_group(ExportGroup.READY) == []
    assert [p.value for p in missing_parts(card.phrase)] == missing
