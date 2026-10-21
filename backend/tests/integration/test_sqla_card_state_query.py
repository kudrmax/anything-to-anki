"""The screens' reads of the stored projection: counts by stored sections, done marks, the
revision and the ✨ counts, live rows only."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.by_step import NewCountsByStep, SectionsByStep
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_state_rows import CardStateRow
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.generated_parts import GeneratedParts
from backend.domain.value_objects.generation_kind import GenerationKind
from backend.domain.value_objects.generation_tally import GenerationGroup
from backend.domain.value_objects.ordered_card import OrderedCard
from backend.domain.value_objects.section_tally import SectionTally
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.persistence.sqla_card_state_query import SqlaCardStateQuery
from backend.infrastructure.persistence.sqla_card_state_store import SqlaCardStateStore
from sqlalchemy import text

from tests.integration.conftest import insert_source
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

R = CandidateSection.READY
E = CandidateSection.EXTRA
P = CandidateSection.PROBABLY_KNOWN
V = CandidateSection.REVIEWED
READY_FROM_THIRD_STEP = SectionsByStep((P, P, R, R, R, R, R, R))
ALL_READY = SectionsByStep((R,) * 8)
ALL_EXTRA = SectionsByStep((E,) * 8)
REVIEWED = SectionsByStep((V,) * 8)
NO_NEW_WORDS = NewCountsByStep((0,) * 8)
THIRD_STEP = 3.5
FIRST_STEP = 2.5
BOOK, ARTICLE = 1, 2
# Book: two open cards, one done, one removed; article: one open card.
OPEN_MEANING, OPEN_FAILED, DONE, GONE, ARTICLE_CARD = 1, 2, 3, 4, 5


def _row(
    word_id: int, source_id: int, sections: SectionsByStep, *, is_done: bool = False,
    done: frozenset[GenerationKind] = frozenset(),
    failed: frozenset[GenerationKind] = frozenset(),
) -> CardStateRow:
    return CardStateRow(
        phrase_id=phrase_id_of(word_id), source_id=source_id, word_id=word_id,
        lemma=f"word{word_id}", is_done=is_done, wants_generation=not is_done,
        sections=REVIEWED if is_done else sections, open_sections=sections,
        new_counts=NO_NEW_WORDS,
        generated=GeneratedParts(done, frozenset({GenerationKind.MEDIA}), failed_jobs=failed),
        changes_at=None,
    )


@pytest.fixture()
def query(db_session: Session) -> SqlaCardStateQuery:
    insert_source(db_session, BOOK)
    insert_source(db_session, ARTICLE)
    for word_id in (OPEN_MEANING, OPEN_FAILED, DONE, GONE):
        insert_word(db_session, word_id, source_id=BOOK)
    insert_word(db_session, ARTICLE_CARD, source_id=ARTICLE)
    store = SqlaCardStateStore(db_session)
    revision = store.next_revision()
    store.write_cards([
        _row(OPEN_MEANING, BOOK, READY_FROM_THIRD_STEP, done=frozenset({GenerationKind.MEANING})),
        _row(OPEN_FAILED, BOOK, READY_FROM_THIRD_STEP, failed=frozenset({GenerationKind.MEANING})),
        _row(DONE, BOOK, ALL_READY, is_done=True),
        _row(GONE, BOOK, ALL_EXTRA),
        _row(ARTICLE_CARD, ARTICLE, ALL_READY),
    ], revision)
    store.remove_cards([phrase_id_of(GONE)], store.next_revision())
    db_session.commit()
    return SqlaCardStateQuery(db_session)


def test_tallies_count_the_live_cards_by_their_sections(query: SqlaCardStateQuery) -> None:
    assert query.section_tallies([BOOK, ARTICLE, 99]) == {
        BOOK: SectionTally({READY_FROM_THIRD_STEP: 2, REVIEWED: 1}),
        ARTICLE: SectionTally({ALL_READY: 1}),
    }


def test_the_progress_of_a_tally_follows_the_step(query: SqlaCardStateQuery) -> None:
    book = query.section_tallies([BOOK])[BOOK]
    assert book.progress(FIRST_STEP) == DecisionProgress(decided=1, total=1)
    assert book.progress(THIRD_STEP) == DecisionProgress(decided=1, total=3)
    assert book.cards == 3


def test_done_marks_are_of_the_live_cards(query: SqlaCardStateQuery) -> None:
    assert query.done_of_sources([BOOK]) == {
        phrase_id_of(OPEN_MEANING): False,
        phrase_id_of(OPEN_FAILED): False,
        phrase_id_of(DONE): True,
    }


def test_the_revision_is_the_projections(
    query: SqlaCardStateQuery, db_session: Session,
) -> None:
    before = query.revision()
    assert SqlaCardStateStore(db_session).next_revision() == before + 1
    assert query.revision() == before + 1


def test_generation_counts_the_cards_in_play_by_result_and_job(
    query: SqlaCardStateQuery,
) -> None:
    tallies = query.generation_tallies([BOOK, ARTICLE], lambda s: s.at(THIRD_STEP) is R)

    book = tallies[BOOK]
    assert sorted(book.of(GenerationKind.MEANING), key=repr) == sorted([
        GenerationGroup(done=True, active_job=False, failed_job=False, cards=1, ready=1),
        GenerationGroup(done=False, active_job=False, failed_job=True, cards=1, ready=1),
    ], key=repr)
    assert book.of(GenerationKind.TTS) == (
        GenerationGroup(done=False, active_job=False, failed_job=False, cards=2, ready=2),
    )
    assert book.of(GenerationKind.PRONUNCIATION) == (
        GenerationGroup(done=False, active_job=False, failed_job=False, cards=2, ready=2),
    )
    assert book.of(GenerationKind.MEDIA) == ()
    assert tallies[ARTICLE].of(GenerationKind.MEANING) == (
        GenerationGroup(done=False, active_job=False, failed_job=False, cards=1, ready=1),
    )


def test_readiness_is_the_callers(query: SqlaCardStateQuery) -> None:
    tallies = query.generation_tallies([BOOK], lambda s: s.at(FIRST_STEP) is R)
    assert [group.ready for group in tallies[BOOK].of(GenerationKind.TTS)] == [0]


def test_the_order_rows_are_the_live_cards_with_their_words_facts_and_place(
    query: SqlaCardStateQuery, db_session: Session,
) -> None:
    db_session.execute(text(
        "UPDATE candidates SET occurrences = 4, is_phrasal_verb = 1, zipf_frequency = 4.2,"
        " usage_distribution = '{\"informal\": 0.5}' WHERE id = :id"
    ), {"id": OPEN_MEANING})
    db_session.execute(text(
        "INSERT INTO cefr_breakdowns (candidate_id, decision_method, oxford) VALUES"
        " (:id, 'priority', 'B2')"
    ), {"id": OPEN_MEANING})
    db_session.execute(text(
        "UPDATE phrases SET phrase_position = '[3, 1, 17, 1, 40]', block = 9, line = 9, char = 9"
        " WHERE id = :id"
    ), {"id": phrase_id_of(OPEN_MEANING)})
    db_session.commit()

    rows = {row.phrase_id: row for row in query.order_rows([BOOK])}

    assert set(rows) == {phrase_id_of(i) for i in (OPEN_MEANING, OPEN_FAILED, DONE)}
    assert rows[phrase_id_of(OPEN_MEANING)] == OrderedCard(
        phrase_id=phrase_id_of(OPEN_MEANING), word_id=OPEN_MEANING, source_id=BOOK,
        lemma=f"word{OPEN_MEANING}", pos="NOUN", zipf_frequency=4.2, cefr_level="B2",
        occurrences=4, is_phrasal_verb=True,
        usage_distribution=UsageDistribution({"informal": 0.5}), place=(3, 1, 17),
        is_done=False, sections=READY_FROM_THIRD_STEP, new_counts=NO_NEW_WORDS,
    )
    done = rows[phrase_id_of(DONE)]
    assert (done.is_done, done.sections, done.place, done.cefr_level) == (
        True, REVIEWED, None, None,
    )
    assert done.usage_distribution is None
    assert [row.source_id for row in query.order_rows([ARTICLE, 99])] == [ARTICLE]


def test_what_changed_since_a_revision_holds_the_removed_cards_too(
    query: SqlaCardStateQuery, db_session: Session,
) -> None:
    store = SqlaCardStateStore(db_session)
    seen = query.revision()
    revision = store.next_revision()
    store.write_cards([_row(OPEN_MEANING, BOOK, ALL_EXTRA)], revision)
    store.remove_cards([phrase_id_of(OPEN_FAILED)], revision)
    store.write_cards([_row(ARTICLE_CARD, ARTICLE, ALL_EXTRA)], revision)

    changed = {c.row.phrase_id: c for c in query.changed_since([BOOK], seen)}

    assert set(changed) == {phrase_id_of(OPEN_MEANING), phrase_id_of(OPEN_FAILED)}
    assert changed[phrase_id_of(OPEN_MEANING)].row == _row(OPEN_MEANING, BOOK, ALL_EXTRA)
    assert changed[phrase_id_of(OPEN_FAILED)].removed
    assert {c.revision for c in changed.values()} == {revision}
    assert query.changed_since([BOOK], revision) == []


def test_whether_cards_are_done_by_phrase(query: SqlaCardStateQuery) -> None:
    assert query.done_of_phrases(
        [phrase_id_of(i) for i in (OPEN_MEANING, DONE, GONE)] + [999],
    ) == {phrase_id_of(OPEN_MEANING): False, phrase_id_of(DONE): True}
