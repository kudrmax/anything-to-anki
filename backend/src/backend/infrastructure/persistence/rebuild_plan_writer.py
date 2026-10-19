"""Writes a rebuild plan in the caller's transaction."""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import (
    PhraseModel,
    StoredCandidateModel,
    dump_phrase,
    dump_position,
)
from backend.infrastructure.persistence.phrase_writes import chunks, drop_results

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import Table
    from sqlalchemy.orm import Session

    from backend.domain.services.phrase_selection import SelectionChange
    from backend.domain.services.rebuild_plan import (
        NewWord,
        OccurrenceInsert,
        OccurrenceRekey,
        OccurrenceScoreUpdate,
        OccurrenceTextUpdate,
        RebuildPlan,
        SectionChange,
        WordUpdate,
    )

# The predicate of the partial unique index on the key of auto phrases.
AUTO_ONLY = "origin = 'auto'"


class RebuildPlanWriter:
    """Applies a plan with bulk statements; flushes, never commits."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def apply(self, plan: RebuildPlan) -> list[int]:
        """Returns the ids of the inserted phrases, in the order of the plan's inserts."""
        self._delete_phrases(plan.occ_to_delete)
        self._rekey(plan.occ_to_rekey)
        self._delete_words(plan.words_to_delete)
        self._update_words(plan.words_to_update)
        self._create_words(plan.source_id, plan.words_to_create)
        self._rewrite(plan.occ_to_update_text)
        self._rescore(plan.occ_to_update_score)
        inserted = self._insert(plan.occ_to_insert, self._word_ids(plan.source_id))
        self._select(plan.selection_changes)
        self._restamp(plan.section_changes)
        self._session.flush()
        return inserted

    def _delete_phrases(self, ids: Sequence[int]) -> None:
        for chunk in chunks(ids):
            self._session.execute(delete(PhraseModel).where(PhraseModel.id.in_(chunk)))

    def _rekey(self, rekeys: Sequence[OccurrenceRekey]) -> None:
        if rekeys:
            self._session.execute(
                update(PhraseModel),
                [
                    {"id": r.occurrence_id, "block": r.key.block, "line": r.key.line,
                     "char": r.key.char}
                    for r in rekeys
                ],
            )

    def _delete_words(self, ids: Sequence[int]) -> None:
        for chunk in chunks(ids):
            for word in self._session.scalars(
                select(StoredCandidateModel).where(StoredCandidateModel.id.in_(chunk))
            ):
                self._session.delete(word)
        self._session.flush()

    def _update_words(self, updates: Sequence[WordUpdate]) -> None:
        data = {u.word_id: u.data for u in updates}
        for chunk in chunks(list(data)):
            for word in self._session.scalars(
                select(StoredCandidateModel).where(StoredCandidateModel.id.in_(chunk))
            ):
                word.write_data(data[word.id])
        self._session.flush()

    def _create_words(self, source_id: int, new: Sequence[NewWord]) -> None:
        for planned in new:
            word = StoredCandidateModel(
                source_id=source_id,
                lemma=planned.lemma,
                is_phrasal_verb=planned.is_phrasal_verb,
                status=WordStatus.NEW.value,
            )
            word.write_data(planned.data)
            self._session.add(word)
        self._session.flush()

    def _word_ids(self, source_id: int) -> dict[WordKey, int]:
        rows = self._session.execute(
            select(
                StoredCandidateModel.id,
                StoredCandidateModel.lemma,
                StoredCandidateModel.is_phrasal_verb,
            ).where(StoredCandidateModel.source_id == source_id)
        ).all()
        return {WordKey.of(lemma, phrasal): word_id for word_id, lemma, phrasal in rows}

    def _rewrite(self, updates: Sequence[OccurrenceTextUpdate]) -> None:
        by_id = {u.occurrence_id: u for u in updates}
        reset: list[int] = []
        for chunk in chunks(list(by_id)):
            for phrase in self._session.scalars(
                select(PhraseModel).where(PhraseModel.id.in_(chunk))
            ):
                planned = by_id[phrase.id]
                phrase.source_phrase = _dumped(planned)
                phrase.phrase_position = dump_position(planned.phrase_position)
                phrase.fragment_score = planned.fragment_score
                phrase.earned_section = planned.earned_section.value
                if planned.bump_revision:
                    phrase.revision += 1
                if planned.reset_results:
                    phrase.polished_phrase = None
                    phrase.polish_reverted = False
                    reset.append(phrase.id)
        self._session.flush()
        drop_results(self._session, reset)

    def _rescore(self, updates: Sequence[OccurrenceScoreUpdate]) -> None:
        if updates:
            self._session.execute(
                update(PhraseModel),
                [{"id": u.occurrence_id, "fragment_score": u.fragment_score} for u in updates],
            )

    def _restamp(self, changes: Sequence[SectionChange]) -> None:
        if changes:
            self._session.execute(
                update(PhraseModel),
                [
                    {"id": c.occurrence_id, "earned_section": c.earned_section.value}
                    for c in changes
                ],
            )

    def _insert(
        self, inserts: Sequence[OccurrenceInsert], word_ids: dict[WordKey, int],
    ) -> list[int]:
        """New auto phrases, upserted by their key. A phrase already at the key stays as it
        is, with its id: the plan changes stored phrases only by their id."""
        if not inserts:
            return []
        # The table, not the mapped class: the statement is compiled once and run for every
        # row, where the ORM's bulk path compiles it again for each row of an upsert with
        # RETURNING.
        table = cast("Table", PhraseModel.__table__)
        phrases = table.c
        upsert = sqlite_insert(table).on_conflict_do_update(
            index_elements=[phrases.candidate_id, phrases.block, phrases.line, phrases.char],
            index_where=text(AUTO_ONLY),
            set_={"candidate_id": phrases.candidate_id},
        ).returning(phrases.id, sort_by_parameter_order=True)
        rows = [_new_row(planned, word_ids[planned.word]) for planned in inserts]
        return list(self._session.scalars(upsert, rows))

    def _select(self, changes: Sequence[SelectionChange]) -> None:
        """Only selection marks change: a mark the user put is never cleared nor replaced."""
        cleared = [i for change in changes for i in change.clear_selection]
        chosen = [change.set_selection for change in changes if change.set_selection is not None]
        for chunk in chunks(cleared):
            self._session.execute(
                update(PhraseModel)
                .where(PhraseModel.id.in_(chunk), PhraseModel.shown_by == ShownBy.SELECTION.value)
                .values(shown_by=None)
            )
        for chunk in chunks(chosen):
            self._session.execute(
                update(PhraseModel)
                .where(PhraseModel.id.in_(chunk), PhraseModel.shown_by.is_(None))
                .values(shown_by=ShownBy.SELECTION.value)
            )


def _new_row(planned: OccurrenceInsert, word_id: int) -> dict[str, object]:
    occurrence = planned.occurrence
    return {
        "candidate_id": word_id,
        "block": occurrence.key.block,
        "line": occurrence.key.line,
        "char": occurrence.key.char,
        "source_phrase": dump_phrase(occurrence.phrase),
        "phrase_position": dump_position(occurrence.phrase_position),
        "fragment_score": occurrence.fragment_score,
        "origin": OccurrenceOrigin.AUTO.value,
        "shown_by": ShownBy.SELECTION.value if planned.shown else None,
        "earned_section": planned.earned_section.value,
    }


def _dumped(planned: OccurrenceTextUpdate) -> str:
    stored = dump_phrase(planned.phrase)
    assert stored is not None
    return stored
