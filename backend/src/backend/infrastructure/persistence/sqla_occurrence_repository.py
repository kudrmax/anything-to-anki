from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from sqlalchemy import exists, or_, select, update

from backend.domain.ports.occurrence_repository import OccurrenceRepository
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.word_row import WordRow
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import (
    AnkiSyncedCardModel,
    CandidateClozeModel,
    CandidateMeaningModel,
    CandidateMediaModel,
    CandidatePronunciationModel,
    CandidateTTSModel,
    JobModel,
    PhraseModel,
    StoredCandidateModel,
    dump_phrase,
    dump_position,
    load_phrase,
    load_position,
)
from backend.infrastructure.persistence.phrase_writes import PhraseWords, drop_results
from backend.infrastructure.persistence.rebuild_plan_writer import RebuildPlanWriter

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.entities.candidate_tts import CandidateTTS
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.services.rebuild_plan import RebuildPlan
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin_kind import DecisionKind

ACTIVE_JOB_STATUSES = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)


@dataclass(frozen=True)
class PhraseResults:
    """What was made for one phrase."""

    meaning: CandidateMeaning | None = None
    media: CandidateMedia | None = None
    tts: CandidateTTS | None = None
    cloze: CandidateCloze | None = None


class PhraseResultsReader:
    """Loads the results of phrases in one query per kind."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def by_phrase(self, phrase_words: dict[int, int]) -> dict[int, PhraseResults]:
        """`phrase_words`: phrase id → its word id. Results come keyed by phrase id."""
        ids = list(phrase_words)
        if not ids:
            return {}
        ipa = self.ipa_by_word(list(set(phrase_words.values())))
        meanings = {
            row.phrase_id: row.to_entity(
                phrase_words[row.phrase_id], ipa.get(phrase_words[row.phrase_id]),
            )
            for row in self._rows(CandidateMeaningModel, ids)
        }
        medias = {
            row.phrase_id: row.to_entity(phrase_words[row.phrase_id])
            for row in self._rows(CandidateMediaModel, ids)
        }
        ttses = {
            row.phrase_id: row.to_entity(phrase_words[row.phrase_id])
            for row in self._rows(CandidateTTSModel, ids)
        }
        clozes = {
            row.phrase_id: row.to_entity(phrase_words[row.phrase_id])
            for row in self._rows(CandidateClozeModel, ids)
        }
        return {
            phrase_id: PhraseResults(
                meaning=meanings.get(phrase_id),
                media=medias.get(phrase_id),
                tts=ttses.get(phrase_id),
                cloze=clozes.get(phrase_id),
            )
            for phrase_id in ids
        }

    def ipa_by_word(self, word_ids: list[int]) -> dict[int, str | None]:
        if not word_ids:
            return {}
        rows = self._session.execute(
            select(CandidatePronunciationModel.candidate_id, CandidatePronunciationModel.ipa)
            .where(CandidatePronunciationModel.candidate_id.in_(word_ids))
        ).all()
        return {word_id: ipa for word_id, ipa in rows}

    def _rows[M: (
        CandidateMeaningModel, CandidateMediaModel, CandidateTTSModel, CandidateClozeModel,
    )](self, model: type[M], phrase_ids: list[int]) -> list[M]:
        return list(self._session.scalars(select(model).where(model.phrase_id.in_(phrase_ids))))


class SqlaOccurrenceRepository(OccurrenceRepository):
    """SQLAlchemy implementation of OccurrenceRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._results = PhraseResultsReader(session)
        self._words = PhraseWords(session)
        self._plans = RebuildPlanWriter(session, self._words)

    def by_source(self, source_id: int) -> list[Occurrence]:
        return self._occurrences(self._of_source(source_id))

    def projection(self, source_id: int) -> list[OccurrenceRow]:
        has_results = or_(
            PhraseModel.polished_phrase.is_not(None),
            exists().where(
                CandidateMeaningModel.phrase_id == PhraseModel.id,
                CandidateMeaningModel.meaning.is_not(None),
                CandidateMeaningModel.meaning != "",
            ),
            exists().where(
                CandidateMediaModel.phrase_id == PhraseModel.id,
                or_(
                    CandidateMediaModel.screenshot_path.is_not(None),
                    CandidateMediaModel.audio_path.is_not(None),
                ),
            ),
            exists().where(
                CandidateTTSModel.phrase_id == PhraseModel.id,
                CandidateTTSModel.audio_path.is_not(None),
            ),
            exists().where(CandidateClozeModel.phrase_id == PhraseModel.id),
        )
        rows = self._session.execute(
            select(
                PhraseModel,
                has_results.label("has_results"),
                self._exported().label("exported"),
                self._has_active_job().label("has_active_job"),
            ).where(self._of_source(source_id)).order_by(PhraseModel.id)
        ).all()
        return [
            OccurrenceRow(
                id=phrase.id,
                candidate_id=phrase.candidate_id,
                key=phrase.key(),
                origin=OccurrenceOrigin(phrase.origin),
                shown_by=ShownBy(phrase.shown_by) if phrase.shown_by is not None else None,
                skipped=phrase.skipped,
                is_decision=phrase.is_decision,
                revision=phrase.revision,
                edited_by_user=phrase.edited_by_user,
                has_results=bool(results),
                exported=bool(exported),
                has_active_job=bool(active),
                text_hash=OccurrenceRow.hash_text(json.loads(phrase.source_phrase)["text"]),
                fragment_score=phrase.fragment_score,
                shows_polish=phrase.polished_phrase is not None and not phrase.polish_reverted,
                phrase_hash=OccurrenceRow.hash_phrase(
                    _required(phrase.source_phrase), load_position(phrase.phrase_position),
                ),
            )
            for phrase, results, exported, active in rows
        ]

    def get(self, occurrence_id: int) -> Occurrence | None:
        found = self._occurrences(PhraseModel.id == occurrence_id)
        return found[0] if found else None

    def add(self, occurrence: Occurrence) -> Occurrence:
        model = PhraseModel.from_entity(occurrence)
        self._session.add(model)
        self._session.flush()
        self._words.rewrite({model.id: model.shown_text})
        return model.to_entity()

    def write_text(
        self,
        occurrence_id: int,
        phrase: Phrase,
        position: DocumentPosition | None,
        *,
        polished: Phrase | None = None,
        polish_reverted: bool = False,
        bump_revision: bool = False,
    ) -> None:
        model = self._session.get(PhraseModel, occurrence_id)
        if model is None:
            return
        model.source_phrase = _dumped(phrase)
        model.phrase_position = dump_position(position)
        model.polished_phrase = dump_phrase(polished)
        model.polish_reverted = polish_reverted
        if bump_revision:
            model.revision += 1
        self._session.flush()
        self._words.rewrite({model.id: model.shown_text})

    def set_shown(self, ids: list[int], shown_by: ShownBy | None) -> None:
        if not ids:
            return
        self._session.execute(
            update(PhraseModel)
            .where(PhraseModel.id.in_(ids))
            .values(shown_by=shown_by.value if shown_by is not None else None)
        )
        self._session.flush()

    def set_skipped(self, occurrence_id: int, skipped: bool) -> None:
        self._session.execute(
            update(PhraseModel).where(PhraseModel.id == occurrence_id).values(skipped=skipped)
        )
        self._session.flush()

    def set_decision(
        self, candidate_id: int, occurrence_id: int | None, kind: DecisionKind | None,
    ) -> None:
        self._session.execute(
            update(PhraseModel)
            .where(PhraseModel.candidate_id == candidate_id, PhraseModel.is_decision.is_(True))
            .values(is_decision=False, decision_kind=None)
        )
        if occurrence_id is not None:
            self._session.execute(
                update(PhraseModel)
                .where(PhraseModel.id == occurrence_id, PhraseModel.candidate_id == candidate_id)
                .values(
                    is_decision=True, decision_kind=kind.value if kind is not None else None,
                )
            )
        self._session.flush()

    def reset_results(self, occurrence_id: int) -> None:
        drop_results(self._session, [occurrence_id])
        phrase = self._session.get(PhraseModel, occurrence_id)
        if phrase is not None:
            phrase.polished_phrase = None
            phrase.polish_reverted = False
            self._session.flush()
            self._words.rewrite({phrase.id: phrase.shown_text})
        self._session.flush()

    def word_rows(self, source_id: int) -> list[WordRow]:
        words = self._session.scalars(
            select(StoredCandidateModel)
            .where(StoredCandidateModel.source_id == source_id)
            .order_by(StoredCandidateModel.id)
        ).unique()
        return [
            WordRow(
                id=word.id,
                lemma=word.lemma,
                is_phrasal_verb=word.is_phrasal_verb,
                status=WordStatus(word.status),
                data=word.word_data(),
            )
            for word in words
        ]

    def apply_plan(self, plan: RebuildPlan) -> None:
        self._plans.apply(plan)

    def shown_by_word(self, source_id: int) -> dict[int, list[Occurrence]]:
        by_word: dict[int, list[Occurrence]] = {}
        for occurrence in self._occurrences(
            self._of_source(source_id), PhraseModel.shown_by.is_not(None),
        ):
            by_word.setdefault(occurrence.candidate_id, []).append(occurrence)
        return by_word

    # ── private helpers ────────────────────────────────────────────────

    def _occurrences(self, *where: ColumnElement[bool]) -> list[Occurrence]:
        rows = self._session.execute(
            select(
                PhraseModel,
                self._exported().label("exported"),
                self._has_active_job().label("has_active_job"),
            ).where(*where).order_by(PhraseModel.id)
        ).all()
        results = self._results.by_phrase(
            {phrase.id: phrase.candidate_id for phrase, _, _ in rows}
        )
        occurrences: list[Occurrence] = []
        for phrase, exported, active in rows:
            made = results[phrase.id]
            occurrences.append(replace(
                phrase.to_entity(),
                meaning=made.meaning,
                media=made.media,
                tts=made.tts,
                cloze=made.cloze,
                exported=bool(exported),
                has_active_job=bool(active),
            ))
        return occurrences

    @staticmethod
    def _of_source(source_id: int) -> ColumnElement[bool]:
        return PhraseModel.candidate_id.in_(
            select(StoredCandidateModel.id).where(StoredCandidateModel.source_id == source_id)
        )

    @staticmethod
    def _exported() -> ColumnElement[bool]:
        return exists().where(AnkiSyncedCardModel.phrase_id == PhraseModel.id)

    @staticmethod
    def _has_active_job() -> ColumnElement[bool]:
        return exists().where(
            JobModel.phrase_id == PhraseModel.id, JobModel.status.in_(ACTIVE_JOB_STATUSES),
        )


def _required(stored: str) -> Phrase:
    phrase = load_phrase(stored)
    assert phrase is not None
    return phrase


def _dumped(phrase: Phrase) -> str:
    stored = dump_phrase(phrase)
    assert stored is not None
    return stored
