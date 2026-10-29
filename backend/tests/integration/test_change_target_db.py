"""Change target: other words of a card's phrase become its target, as a card made anew."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.change_target import ChangeTargetUseCase
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.entities.token_data import TokenData
from backend.domain.exceptions import TargetChangeRefusedError, TargetNotInPhraseError
from backend.domain.value_objects.card_choice import CardChoice
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork

from tests.candidate_sorter_support import section_stamper
from tests.decision_support import Decisions
from tests.lock_support import free_lock
from tests.phrase_support import phrase
from tests.source_rebuild_support import LINES, SOURCE, Bench, at, word

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

LEMMAS = {"glared": "glare", "lingered": "linger"}
WEIGHT_UNKNOWN = 10
ME = 3  # "He glared at me." → He, glared, at, me
ME_CHAR = LINES[0].index("me")


def _token(text: str) -> TokenData:
    return TokenData(
        index=0, text=text, lemma=LEMMAS.get(text.lower(), text.lower()), pos="NOUN",
        tag="NN", head_index=0, children_indices=(), is_punct=False, is_stop=False,
        is_alpha=True, is_propn=False, sent_index=0,
    )


class Change:
    """Changing targets of the bench's cards; glare is found on lines 0, 1 and 5."""

    def __init__(self, bench: Bench) -> None:
        self.bench = bench
        analyzer = MagicMock()
        analyzer.analyze.side_effect = lambda text: [_token(w.strip(".,")) for w in text.split()]
        detector = MagicMock()
        detector.detect.return_value = []
        classifier = MagicMock()
        classifier.classify_detailed.return_value = CEFRBreakdown(
            final_level=CEFRLevel.C1, decision_method="voting", priority_votes=[], votes=[],
        )
        frequency = MagicMock()
        frequency.get_zipf_value.return_value = 3.0
        decisions = Decisions(bench.session)
        self.use_case = ChangeTargetUseCase(
            occurrence_repo=bench.occurrences,
            candidate_repo=bench.candidates,
            document_repo=SqlaDocumentRepository(bench.session),
            job_repo=bench.jobs,
            word_states=decisions.word_states,
            text_analyzer=analyzer,
            cefr_classifier=classifier,
            frequency_provider=frequency,
            phrasal_verb_detector=detector,
            stamper=section_stamper(SqlaSettingsRepository(
                bench.session, SessionChangeRecorder(bench.session),
            )),
            lock=free_lock(),
            card_views=MagicMock(),
            decide_phrase=decisions.decide_phrase(),
            unit_of_work=SqlaUnitOfWork(bench.session, decisions.scope),
            weight_unknown=WEIGHT_UNKNOWN,
        )

    def to(self, phrase_id: int, *target: int) -> None:
        self.use_case.execute(phrase_id, list(target))
        self.bench.session.commit()


@pytest.fixture
def bench(db_session: Session) -> Bench:
    bench = Bench(db_session)
    bench.processed(word("glare", at(0, 10.0), at(1, 20.0), at(5, 30.0)))
    return bench


def _of(bench: Bench, lemma: str) -> list[Occurrence]:
    [found] = [w for w in bench.occurrences.word_rows(SOURCE) if w.lemma == lemma]
    return bench.occurrences.of_word(found.id)


def _card(bench: Bench) -> int:
    return bench.phrase_on("glare", 0).id


def _polish(bench: Bench, phrase_id: int, text: str) -> None:
    occ = bench.occurrences.get(phrase_id)
    assert occ is not None
    bench.occurrences.write_text(
        phrase_id, occ.source_phrase, occ.phrase_position,
        earned_section=occ.earned_section,
        polished=phrase(text, lemmas=LEMMAS).with_target(occ.source_phrase.target),
    )
    bench.session.commit()


# ── the new card ──────────────────────────────────────────────────────


def test_the_new_target_gets_a_manual_card_at_its_place(bench: Bench) -> None:
    Change(bench).to(_card(bench), ME)

    [made] = _of(bench, "me")
    assert made.origin is OccurrenceOrigin.MANUAL
    assert made.shown_by is ShownBy.USER
    assert made.source_phrase.text == LINES[0]
    assert made.phrase.target_text() == "me"
    assert made.polished_phrase is None
    assert made.key == OccurrenceKey(block=0, line=0, char=ME_CHAR)


def test_the_new_card_has_its_meaning_queued(bench: Bench) -> None:
    Change(bench).to(_card(bench), ME)

    [made] = _of(bench, "me")
    jobs = bench.jobs.get_jobs_by_status([JobStatus.QUEUED])
    assert (JobType.MEANING, made.id) in [(j.job_type, j.phrase_id) for j in jobs]


def test_several_words_apart_make_one_target(bench: Bench) -> None:
    Change(bench).to(_card(bench), 0, ME)

    [new] = [w.lemma for w in bench.occurrences.word_rows(SOURCE) if w.lemma != "glare"]
    [made] = _of(bench, new)
    assert made.phrase.target == (0, ME)
    assert made.phrase.target_text() == "He me"


def test_a_word_written_into_the_edited_text_is_a_target_with_no_place(bench: Bench) -> None:
    card = _card(bench)
    _polish(bench, card, "He glared at my cat.")

    Change(bench).to(card, 4)

    [made] = _of(bench, "cat")
    assert made.phrase_position is None
    assert made.key is None
    assert made.source_phrase.text == "He glared at my cat."
    assert made.polished_phrase is not None
    assert made.phrase.target_text() == "cat"


def test_a_target_the_source_holds_keeps_its_place_and_the_edited_text(
    bench: Bench,
) -> None:
    card = _card(bench)
    _polish(bench, card, "He glared angrily at me.")

    Change(bench).to(card, 4)

    [made] = _of(bench, "me")
    assert made.key == OccurrenceKey(block=0, line=0, char=ME_CHAR)
    assert made.source_phrase.text == LINES[0]
    assert made.source_phrase.target_text() == "me"
    assert made.phrase.text == "He glared angrily at me."
    assert made.phrase.target_text() == "me"


# ── the old card ──────────────────────────────────────────────────────


def test_the_old_card_is_hidden_and_its_word_shows_its_next_phrase(bench: Bench) -> None:
    card = _card(bench)

    Change(bench).to(card, ME)

    old = bench.occurrences.get(card)
    assert old is not None
    assert old.shown_by is None
    assert old.removed_by_user
    assert old.choice is CardChoice.NONE
    assert bench.shown_lines("glare") == [1]


def test_rebuild_never_brings_the_old_card_back(bench: Bench) -> None:
    card = _card(bench)
    Change(bench).to(card, ME)

    bench.rebuild().execute(SOURCE, RebuildMode.RECUT)

    assert bench.shown_lines("glare") == [1]
    assert [o.shown_by for o in _of(bench, "me")] == [ShownBy.USER]


def test_an_undone_decision_elsewhere_never_brings_the_old_card_back(bench: Bench) -> None:
    card = _card(bench)
    decision = bench.phrase_on("glare", 5).id
    bench.decide_learn("glare", decision)
    Change(bench).to(card, ME)

    bench.set_choice(decision, "none")
    bench.rebuild().execute(SOURCE, RebuildMode.RECUT)

    assert 0 not in bench.shown_lines("glare")


def test_adding_the_old_word_back_at_its_place_makes_a_new_card(bench: Bench) -> None:
    card = _card(bench)
    Change(bench).to(card, ME)
    [made] = _of(bench, "me")
    assert made.id is not None

    Change(bench).to(made.id, 1)

    at_line = [o for o in _of(bench, "glare") if o.key is not None and o.key.line == 0]
    assert [(o.id == card, o.shown_by) for o in at_line] == [
        (True, None), (False, ShownBy.USER),
    ]


def test_a_card_with_a_decision_is_refused(bench: Bench) -> None:
    card = _card(bench)
    bench.decide_learn("glare", card)

    with pytest.raises(TargetChangeRefusedError):
        Change(bench).to(card, ME)


def test_the_same_target_changes_nothing(bench: Bench) -> None:
    card = _card(bench)

    Change(bench).to(card, 1)

    assert bench.shown_lines("glare") == [0]
    assert len(bench.occurrences.word_rows(SOURCE)) == 1


def test_no_words_is_refused(bench: Bench) -> None:
    with pytest.raises(TargetNotInPhraseError):
        Change(bench).to(_card(bench))
