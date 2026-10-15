"""Applying a rebuild plan: phrases keep their ids, texts and words follow the analysis,
results go only where the plan says, and a second rebuild has nothing to do."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.services.phrase_selection import SelectionChange
from backend.domain.services.rebuild_plan import OccurrenceInsert, RebuildPlan, plan_rebuild
from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.phrase_origin_kind import ShownBy
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import PhraseModel, PhraseWordModel
from backend.infrastructure.persistence.phrase_writes import SQL_IN_CHUNK
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import select, text

from tests.integration.conftest import insert_source
from tests.rebuild_support import breakdown, built, occ

if TYPE_CHECKING:
    from backend.domain.value_objects.built_analysis import BuiltWord
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

SOURCE = 1
OTHER_SOURCE = 2
FIRST = "He glared at me."
CHANGED = "She glared back."


@pytest.fixture
def repo(db_session: Session) -> SqlaOccurrenceRepository:
    insert_source(db_session, SOURCE)
    insert_source(db_session, OTHER_SOURCE)
    db_session.flush()
    return SqlaOccurrenceRepository(db_session)


def _plan(
    repo: SqlaOccurrenceRepository, analysed: list[BuiltWord], *, include_open: bool = False,
) -> RebuildPlan:
    return plan_rebuild(
        SOURCE, repo.projection(SOURCE), repo.word_rows(SOURCE), analysed, include_open,
    )


def _rebuild(
    repo: SqlaOccurrenceRepository, analysed: list[BuiltWord], *, include_open: bool = False,
) -> RebuildPlan:
    plan = _plan(repo, analysed, include_open=include_open)
    repo.apply_plan(plan)
    return plan


def _phrases(session: Session) -> dict[int, PhraseModel]:
    session.expire_all()
    return {p.id: p for p in session.scalars(select(PhraseModel))}


def _words_of(session: Session, phrase_id: int) -> set[str]:
    return set(session.scalars(
        select(PhraseWordModel.lemma).where(PhraseWordModel.phrase_id == phrase_id)
    ))


def _meaning(session: Session, phrase_id: int, word_id: int) -> None:
    SqlaCandidateMeaningRepository(session).upsert_for_phrase(phrase_id, CandidateMeaning(
        candidate_id=word_id, meaning="to stare angrily", translation=None, synonyms=None,
        examples=None, ipa=None, generated_at=None,
    ))


def test_a_first_build_creates_words_and_phrases_and_a_second_does_nothing(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    analysed = [
        built("glare", occ(0, 0.5), occ(1, 0.1, text=CHANGED)),
        built("linger", occ(2, 0.3, text="They glared and left.")),
    ]

    plan = _rebuild(repo, analysed)

    assert plan.counts.words_added == 2
    words = {w.lemma: w for w in repo.word_rows(SOURCE)}
    assert set(words) == {"glare", "linger"}
    assert words["glare"].data == analysed[0].data
    assert words["glare"].status is WordStatus.PENDING
    phrases = _phrases(db_session)
    shown = {p.candidate_id: p for p in phrases.values() if p.shown_by == ShownBy.SELECTION}
    assert shown[words["glare"].id].line == 1
    assert {p.origin for p in phrases.values()} == {"auto"}
    assert _words_of(db_session, shown[words["glare"].id].id) == {"she", "glared", "back"}
    assert _plan(repo, analysed).is_empty
    assert repo.word_rows(OTHER_SOURCE) == []


def test_an_untouched_phrase_keeps_its_id_and_takes_the_new_text(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    _rebuild(repo, [built("glare", occ(0, 0.5))])
    [before] = _phrases(db_session).values()
    before_id, before_revision = before.id, before.revision

    _rebuild(repo, [built("glare", occ(0, 0.2, text=CHANGED))])

    [after] = _phrases(db_session).values()
    assert after.id == before_id
    assert (after.revision, after.fragment_score) == (before_revision + 1, 0.2)
    assert _words_of(db_session, after.id) == {"she", "glared", "back"}
    assert _plan(repo, [built("glare", occ(0, 0.2, text=CHANGED))]).is_empty


def test_include_open_resets_the_results_of_a_phrase_whose_text_changed(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    _rebuild(repo, [built("glare", occ(0, 0.5))])
    [phrase] = _phrases(db_session).values()
    _meaning(db_session, phrase.id, phrase.candidate_id)
    changed = [built("glare", occ(0, 0.5, text=CHANGED))]

    assert _plan(repo, changed).is_empty
    plan = _rebuild(repo, changed, include_open=True)

    assert plan.counts.cards_text_reset == 1
    stored = repo.get(phrase.id)
    assert stored is not None
    assert (stored.meaning, stored.revision, stored.source_phrase.text) == (None, 1, CHANGED)
    assert _plan(repo, changed, include_open=True).is_empty


def test_a_lost_word_goes_with_its_phrases_but_a_decided_one_stays(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    _rebuild(repo, [built("glare", occ(0, 0.5)), built("linger", occ(1, 0.5))])
    words = {w.lemma: w.id for w in repo.word_rows(SOURCE)}
    linger_phrase = next(
        p.id for p in _phrases(db_session).values() if p.candidate_id == words["linger"]
    )
    db_session.execute(
        text("UPDATE candidates SET status = 'learn' WHERE id = :id"), {"id": words["linger"]},
    )
    repo.set_decision(words["linger"], linger_phrase, None)

    plan = _rebuild(repo, [])

    assert plan.words_to_delete == (words["glare"],)
    assert [w.lemma for w in repo.word_rows(SOURCE)] == ["linger"]
    assert list(_phrases(db_session)) == [linger_phrase]


def test_the_selection_moves_and_the_old_phrase_keeps_its_results(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    _rebuild(repo, [built("glare", occ(0, 0.5))])
    [old] = _phrases(db_session).values()
    _meaning(db_session, old.id, old.candidate_id)
    analysed = [built("glare", occ(0, 0.5), occ(3, 0.1))]

    _rebuild(repo, analysed)
    assert [p.id for p in _phrases(db_session).values() if p.shown_by] == [old.id]

    _rebuild(repo, analysed, include_open=True)
    phrases = _phrases(db_session)
    [shown] = [p for p in phrases.values() if p.shown_by == ShownBy.SELECTION]
    assert shown.line == 3
    assert phrases[old.id].shown_by is None
    kept = repo.get(old.id)
    assert kept is not None
    assert kept.meaning is not None


def test_word_data_follows_the_analysis(repo: SqlaOccurrenceRepository) -> None:
    _rebuild(repo, [built("glare", occ(0, 0.5))])
    usage = UsageDistribution({"formal": 0.5, "neutral": 0.5})
    levels = breakdown(CEFRLevel.C1, {CEFRLevel.B2: 0.123456, CEFRLevel.C1: 0.876544})
    analysed = [replace(
        built("glare", occ(0, 0.5), occ(1, 0.6), pos="NOUN", zipf=4.25),
        usage_distribution=usage, cefr_breakdown=levels, cefr_level=levels.final_level.name,
    )]

    _rebuild(repo, analysed)

    [stored] = repo.word_rows(SOURCE)
    assert (stored.data.pos, stored.data.zipf_frequency, stored.data.occurrence_count) == (
        "NOUN", 4.25, 2,
    )
    assert stored.data.usage_distribution == usage
    assert stored.data.cefr_breakdown is not None
    assert stored.data.cefr_breakdown.reduced() == levels.reduced()
    assert _plan(repo, analysed).is_empty


def test_a_word_with_a_stored_cefr_breakdown_gets_the_new_one(
    repo: SqlaOccurrenceRepository,
) -> None:
    before = breakdown(CEFRLevel.B2, {CEFRLevel.B2: 1.0})
    after = breakdown(CEFRLevel.C1, {CEFRLevel.C1: 1.0})
    _rebuild(repo, [replace(built("glare", occ(0, 0.5)), cefr_breakdown=before)])

    _rebuild(repo, [replace(built("glare", occ(0, 0.5)), cefr_breakdown=after)])

    [stored] = repo.word_rows(SOURCE)
    assert stored.data.cefr_breakdown is not None
    assert stored.data.cefr_breakdown.reduced() == after.reduced()


def test_an_insert_at_a_taken_key_keeps_the_stored_phrase_and_its_id(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    _rebuild(repo, [built("glare", occ(0, 0.5))])
    [phrase] = _phrases(db_session).values()
    phrase_id = phrase.id

    repo.apply_plan(RebuildPlan(source_id=SOURCE, occ_to_insert=(OccurrenceInsert(
        word=WordKey.of("glare", is_phrasal_verb=False),
        occurrence=occ(0, 0.3, text=CHANGED), shown=False,
    ),)))

    [after] = _phrases(db_session).values()
    assert (after.id, after.fragment_score) == (phrase_id, 0.5)
    assert _words_of(db_session, phrase_id) == {"he", "glared", "at", "me"}


def test_selection_changes_never_touch_a_mark_the_user_put(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    _rebuild(repo, [built("glare", occ(0, 0.5), occ(1, 0.6))])
    phrases = _phrases(db_session)
    shown = next(p.id for p in phrases.values() if p.shown_by is not None)
    hidden = next(p.id for p in phrases.values() if p.shown_by is None)
    repo.set_shown([shown, hidden], ShownBy.USER)

    repo.apply_plan(RebuildPlan(source_id=SOURCE, selection_changes=(
        SelectionChange(set_selection=hidden, clear_selection=(shown,)),
    )))

    assert {p.shown_by for p in _phrases(db_session).values()} == {ShownBy.USER.value}


def test_a_book_sized_word_is_written_in_chunks(
    repo: SqlaOccurrenceRepository, db_session: Session,
) -> None:
    many = SQL_IN_CHUNK + 100
    analysed = [built("glare", *(occ(line, 0.5) for line in range(many)))]

    _rebuild(repo, analysed)
    _rebuild(repo, [built("glare", *(occ(line, 0.4) for line in range(many)))])

    phrases = _phrases(db_session)
    assert len(phrases) == many
    assert {p.fragment_score for p in phrases.values()} == {0.4}
    assert _rebuild(repo, []).words_to_delete != ()
    assert _phrases(db_session) == {}
