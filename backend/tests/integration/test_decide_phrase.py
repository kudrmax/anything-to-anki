"""Decisions on a word through its phrases, in a real database."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
from backend.application.utils.decided_elsewhere import DecidedElsewhere
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.word_decision import WordDecision
from backend.domain.exceptions import (
    AlreadyInAnkiError,
    CardDecisionLockedError,
    DecidedElsewhereError,
    PhraseNotFoundError,
)
from backend.domain.services.card_decision import DecisionAction
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.elsewhere import Elsewhere
from backend.domain.value_objects.phrase_origin_kind import (
    DecisionKind,
    OccurrenceOrigin,
    ShownBy,
)
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.sqla_anki_sync_repository import SqlaAnkiSyncRepository
from backend.infrastructure.persistence.sqla_candidate_cloze_repository import (
    SqlaCandidateClozeRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_learning_query import SqlaLearningQuery
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)

from tests.phrase_support import phrase
from tests.vocabulary_support import user_vocabulary
from tests.word_support import insert_word

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

WORD = 1
FIRST = 1
LEMMA = "glare"
LEARN, CLOZE, KNOWN = DecisionAction.LEARN, DecisionAction.CLOZE, DecisionAction.KNOWN
SKIP, UNSKIP, PENDING = DecisionAction.SKIP, DecisionAction.UNSKIP, DecisionAction.PENDING


class Bench:
    """One word of source 1 with two shown phrases: FIRST and `second`."""

    def __init__(self, session: Session) -> None:
        self.session = session
        insert_word(session, WORD, lemma=LEMMA, pos="VERB", phrase_text="He glared at me.")
        self.occurrences = SqlaOccurrenceRepository(session)
        self.candidates = SqlaCandidateRepository(session)
        self.clozes = SqlaCandidateClozeRepository(session)
        self.second = self._add_phrase("She glared back.")
        self.known_words = MagicMock()
        self.known_words.get_all_pairs.return_value = set()
        self.decisions = MagicMock()
        self.review_status = MagicMock()
        self.learning = SqlaLearningQuery(session)

    def _add_phrase(self, text: str) -> int:
        added = self.occurrences.add(Occurrence(
            candidate_id=WORD, origin=OccurrenceOrigin.MANUAL,
            source_phrase=phrase(text, "glared"), phrase_position=None, key=None,
            fragment_score=None, shown_by=ShownBy.USER,
        ))
        assert added.id is not None
        return added.id

    def use_case(self) -> DecidePhraseUseCase:
        vocabulary = user_vocabulary(self.known_words)
        return DecidePhraseUseCase(
            occurrence_repo=self.occurrences,
            candidate_repo=self.candidates,
            vocabulary=vocabulary,
            decision_repo=self.decisions,
            review_status=self.review_status,
            cloze_repo=self.clozes,
            decided_elsewhere=DecidedElsewhere(vocabulary, self.learning),
        )

    def decide(self, phrase_id: int, action: DecisionAction) -> None:
        self.use_case().execute(phrase_id, action)

    def word_status(self) -> WordStatus:
        [row] = [w for w in self.occurrences.word_rows(1) if w.id == WORD]
        return row.status

    def phrase(self, phrase_id: int) -> Occurrence:
        found = self.occurrences.get(phrase_id)
        assert found is not None
        return found

    def export(self, phrase_id: int) -> None:
        SqlaAnkiSyncRepository(self.session).mark_synced(WORD, 900, phrase_id)

    def give_cloze(self, phrase_id: int) -> None:
        self.clozes.upsert_for_phrase(phrase_id, CandidateCloze(
            candidate_id=WORD, hidden_word_indices=(1,), hint_kind=ClozeHintKind.NONE,
            custom_hint=None, phrase="He glared at me.",
        ))


@pytest.fixture
def bench(db_session: Session, source_id: int) -> Bench:
    del source_id
    return Bench(db_session)


# ── Learn / Cloze / Known decide the word ─────────────────────────────


def test_learn_decides_the_word_on_that_phrase(bench: Bench) -> None:
    bench.decide(bench.second, LEARN)

    assert bench.word_status() is WordStatus.LEARN
    assert bench.phrase(bench.second).is_decision
    assert bench.phrase(bench.second).decision_kind is DecisionKind.LEARN
    assert not bench.phrase(FIRST).is_decision
    bench.review_status.refresh.assert_called_once_with(1)
    bench.decisions.record.assert_called_once_with(
        WordDecision(lemma=LEMMA, zipf_frequency=3.0, is_known=False),
    )


def test_cloze_decides_the_word_as_a_cloze(bench: Bench) -> None:
    bench.decide(FIRST, CLOZE)

    assert bench.word_status() is WordStatus.LEARN
    assert bench.phrase(FIRST).decision_kind is DecisionKind.CLOZE


def test_known_marks_the_word_known(bench: Bench) -> None:
    bench.decide(FIRST, KNOWN)

    assert bench.word_status() is WordStatus.KNOWN
    assert bench.phrase(FIRST).is_decision
    bench.known_words.add.assert_called_once_with(LEMMA, "VERB")
    bench.review_status.refresh_all.assert_called_once()


@pytest.mark.parametrize("action", [LEARN, CLOZE, KNOWN, SKIP, PENDING])
def test_the_sibling_card_of_a_decided_word_is_locked(
    bench: Bench, action: DecisionAction,
) -> None:
    bench.decide(FIRST, KNOWN)

    with pytest.raises(CardDecisionLockedError):
        bench.decide(bench.second, action)

    assert bench.word_status() is WordStatus.KNOWN
    assert bench.phrase(FIRST).is_decision
    assert not bench.phrase(bench.second).skipped


def test_known_is_undone_on_the_decision_phrase(bench: Bench) -> None:
    bench.decide(FIRST, KNOWN)

    bench.decide(FIRST, PENDING)

    assert bench.word_status() is WordStatus.PENDING
    assert not bench.phrase(FIRST).is_decision
    bench.known_words.remove_by_lemma.assert_called_once_with(LEMMA, "VERB")
    bench.decisions.forget.assert_called_once_with(LEMMA)


def test_the_decision_changes_on_its_card(bench: Bench) -> None:
    bench.decide(FIRST, LEARN)

    bench.decide(FIRST, KNOWN)

    assert bench.word_status() is WordStatus.KNOWN
    assert bench.phrase(FIRST).is_decision


# ── Skip ──────────────────────────────────────────────────────────────


def test_skip_skips_the_phrase_only(bench: Bench) -> None:
    bench.decide(FIRST, SKIP)

    assert bench.word_status() is WordStatus.PENDING
    assert bench.phrase(FIRST).skipped
    assert not bench.phrase(bench.second).skipped
    bench.decisions.record.assert_not_called()


def test_skip_on_the_decision_card_undoes_and_skips(bench: Bench) -> None:
    bench.decide(FIRST, LEARN)

    bench.decide(FIRST, SKIP)

    assert bench.word_status() is WordStatus.PENDING
    assert bench.phrase(FIRST).skipped
    assert not bench.phrase(FIRST).is_decision
    bench.decisions.forget.assert_called_once_with(LEMMA)


def test_learn_on_a_skipped_phrase_unskips_it(bench: Bench) -> None:
    bench.decide(FIRST, SKIP)

    bench.decide(FIRST, LEARN)

    assert not bench.phrase(FIRST).skipped
    assert bench.phrase(FIRST).is_decision


def test_a_skipped_sibling_of_a_decided_word_can_be_unskipped(bench: Bench) -> None:
    bench.decide(bench.second, SKIP)
    bench.decide(FIRST, LEARN)

    bench.decide(bench.second, UNSKIP)

    assert not bench.phrase(bench.second).skipped
    assert bench.word_status() is WordStatus.LEARN


def test_pending_on_a_skipped_phrase_unskips_it(bench: Bench) -> None:
    bench.decide(FIRST, SKIP)

    bench.decide(FIRST, PENDING)

    assert not bench.phrase(FIRST).skipped


# ── after export ──────────────────────────────────────────────────────


@pytest.mark.parametrize("action", [PENDING, SKIP, CLOZE])
def test_an_exported_decision_stays(bench: Bench, action: DecisionAction) -> None:
    bench.decide(FIRST, LEARN)
    bench.export(FIRST)

    with pytest.raises(AlreadyInAnkiError):
        bench.decide(FIRST, action)

    assert bench.word_status() is WordStatus.LEARN
    assert bench.phrase(FIRST).is_decision


# ── cloze markup ──────────────────────────────────────────────────────


def test_a_new_decision_drops_the_cloze_markup(bench: Bench) -> None:
    bench.decide(FIRST, CLOZE)
    bench.give_cloze(FIRST)

    bench.decide(FIRST, LEARN)

    assert bench.clozes.get_by_phrase_id(FIRST) is None
    assert bench.phrase(FIRST).decision_kind is DecisionKind.LEARN


def test_an_exported_cloze_keeps_its_markup(bench: Bench) -> None:
    bench.decide(FIRST, CLOZE)
    bench.give_cloze(FIRST)
    bench.export(FIRST)

    bench.decide(FIRST, KNOWN)

    assert bench.clozes.get_by_phrase_id(FIRST) is not None
    assert bench.phrase(FIRST).decision_kind is DecisionKind.CLOZE


# ── known or learning via another source ──────────────────────────────


def test_learn_on_a_word_known_elsewhere_is_refused(bench: Bench) -> None:
    bench.known_words.get_all_pairs.return_value = {(LEMMA, "VERB")}

    with pytest.raises(DecidedElsewhereError) as refused:
        bench.decide(FIRST, LEARN)

    assert refused.value.elsewhere is Elsewhere.KNOWN
    assert str(refused.value) == "Already known"
    assert bench.word_status() is WordStatus.PENDING


def test_learn_on_a_word_learning_in_another_source_is_refused(
    bench: Bench, db_session: Session,
) -> None:
    from tests.integration.conftest import insert_source

    insert_source(db_session, 2)
    insert_word(db_session, 50, source_id=2, lemma=LEMMA, status="learn")

    with pytest.raises(DecidedElsewhereError) as refused:
        bench.decide(FIRST, CLOZE)

    assert refused.value.elsewhere is Elsewhere.LEARNING
    assert str(refused.value) == "Already learning from another source"


def test_an_unknown_phrase_is_not_found(bench: Bench) -> None:
    with pytest.raises(PhraseNotFoundError):
        bench.decide(999, LEARN)


# ── the learning query ────────────────────────────────────────────────


def test_learning_lemmas_are_learn_words_not_exported(bench: Bench, db_session: Session) -> None:
    insert_word(db_session, 20, lemma="Linger", status="learn")
    insert_word(db_session, 30, lemma="sway", status="learn")
    insert_word(db_session, 40, lemma="drift", status="known")
    SqlaAnkiSyncRepository(db_session).mark_synced(30, 901, 30)

    assert bench.learning.learning_lemmas() == {"linger"}


def test_a_phrasal_verb_decision_is_not_remembered(bench: Bench, db_session: Session) -> None:
    insert_word(db_session, 60, lemma="give up")

    bench.decide(60, LEARN)

    bench.decisions.record.assert_not_called()
