# backend/src/backend/infrastructure/persistence/sqla_candidate_repository.py
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from backend.domain.entities.occurrence import Occurrence
from backend.domain.ports.candidate_repository import CandidateRepository
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.phrase_origin_kind import (
    DecisionKind,
    OccurrenceOrigin,
    ShownBy,
)
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import (
    CandidateMeaningImageModel,
    CandidatePronunciationModel,
    PhraseModel,
    SourceModel,
    StoredCandidateModel,
    load_phrase,
    load_position,
)
from backend.infrastructure.persistence.primary_phrase import (
    PrimaryPhrases,
    primary_phrase_id,
    status_of,
)
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    PhraseResultsReader,
    SqlaOccurrenceRepository,
)

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement
    from sqlalchemy.orm import Session

    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin import PhraseOrigin

DECIDED_STATUSES = (CandidateStatus.LEARN, CandidateStatus.KNOWN)
COLLECTING_ROLES = (SourceRole.TOPIC.value, SourceRole.SAVED_PHRASES.value)


class SqlaCandidateRepository(CandidateRepository):
    """SQLAlchemy implementation of CandidateRepository: the words of sources.

    A word is read through its primary phrase (see primary_phrase), with the results of
    that phrase and the word's pronunciation and picture attached.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._occurrences = SqlaOccurrenceRepository(session)
        self._primary = PrimaryPhrases(session)
        self._results = PhraseResultsReader(session)

    # TRANSITIONAL(words-phrases): removed in Task 10
    def create_batch(self, candidates: list[StoredCandidate]) -> list[StoredCandidate]:
        """Each candidate becomes a phrase of its word; the word is created if it is new."""
        created: list[StoredCandidate] = []
        for candidate in candidates:
            word = self._word_of(candidate)
            is_new_word = word is None
            if word is None:
                word = StoredCandidateModel.from_entity(candidate)
                if candidate.status is CandidateStatus.SKIP:
                    word.status = CandidateStatus.PENDING.value
                self._session.add(word)
                self._session.flush()
            origin = _origin_of(
                candidate, is_new_word=is_new_word, collects=self._collects(candidate.source_id),
            )
            decided = is_new_word and candidate.status in DECIDED_STATUSES
            self._occurrences.add(Occurrence(
                candidate_id=word.id,
                origin=origin,
                source_phrase=candidate.source_phrase,
                phrase_position=candidate.phrase_position,
                key=candidate.occurrence_key,
                fragment_score=candidate.fragment_score,
                shown_by=ShownBy.SELECTION if origin is OccurrenceOrigin.AUTO else ShownBy.USER,
                skipped=candidate.status is CandidateStatus.SKIP,
                is_decision=decided,
                decision_kind=DecisionKind.LEARN if decided else None,
                polished_phrase=candidate.polished_phrase,
                polish_reverted=candidate.polish_reverted,
            ))
            created.append(self._view([word])[0])
        return created

    def add_word(self, word: StoredCandidate) -> int:
        model = StoredCandidateModel.from_entity(word)
        model.status = WordStatus.PENDING.value
        self._session.add(model)
        self._session.flush()
        return model.id

    def set_word_status(self, candidate_id: int, status: WordStatus) -> None:
        self._session.execute(
            update(StoredCandidateModel)
            .where(StoredCandidateModel.id == candidate_id)
            .values(status=status.value)
        )
        self._session.flush()

    def get_by_source(self, source_id: int) -> list[StoredCandidate]:
        return self._read(StoredCandidateModel.source_id == source_id)

    def get_by_id(self, candidate_id: int) -> StoredCandidate | None:
        found = self._read(StoredCandidateModel.id == candidate_id)
        return found[0] if found else None

    # TRANSITIONAL(words-phrases): removed in Task 10
    def set_origin(self, candidate_id: int, origin: PhraseOrigin | None) -> None:
        word = self._session.get(StoredCandidateModel, candidate_id)
        if word is None:
            return
        word.origin_kind = origin.kind.value if origin is not None else None
        word.origin_title = origin.source_title if origin is not None else None
        self._session.flush()

    # TRANSITIONAL(words-phrases): removed in Task 10
    def count_by_status(self, status: CandidateStatus) -> int:
        stmt = (
            select(func.count(StoredCandidateModel.id))
            .join(PhraseModel, PhraseModel.id == primary_phrase_id(StoredCandidateModel.id))
            .where(*_has_status(status))
        )
        return self._session.execute(stmt).scalar() or 0

    def count_all(self) -> int:
        result = self._session.query(func.count(StoredCandidateModel.id)).scalar()
        return result or 0

    # TRANSITIONAL(words-phrases): removed in Task 10
    def set_polished_phrase(self, candidate_id: int, phrase: Phrase | None) -> None:
        primary = self._primary_model(candidate_id)
        if primary is not None:
            self._occurrences.write_text(
                primary.id, _required(primary.source_phrase),
                load_position(primary.phrase_position), polished=phrase,
            )

    # TRANSITIONAL(words-phrases): removed in Task 10
    def set_polish_reverted(self, candidate_id: int, reverted: bool) -> None:
        primary = self._primary_model(candidate_id)
        if primary is not None:
            self._occurrences.write_text(
                primary.id, _required(primary.source_phrase),
                load_position(primary.phrase_position),
                polished=load_phrase(primary.polished_phrase), polish_reverted=reverted,
            )

    def get_by_ids(self, candidate_ids: list[int]) -> list[StoredCandidate]:
        if not candidate_ids:
            return []
        found = self._read(StoredCandidateModel.id.in_(candidate_ids))
        order_map = {cid: idx for idx, cid in enumerate(candidate_ids)}
        found.sort(key=lambda c: order_map.get(c.id or 0, len(order_map)))
        return found

    def get_by_lemma(self, lemma: str) -> list[StoredCandidate]:
        return self._read(func.lower(StoredCandidateModel.lemma) == lemma.lower())

    # TRANSITIONAL(words-phrases): removed in Task 10
    def get_all_by_status(self, status: CandidateStatus) -> list[StoredCandidate]:
        found = self._read(*_has_status(status), join_primary=True)
        return sorted(found, key=lambda c: c.source_id)

    def get_lemma_map(self, candidate_ids: list[int]) -> dict[int, str]:
        if not candidate_ids:
            return {}
        rows = (
            self._session.query(StoredCandidateModel.id, StoredCandidateModel.lemma)
            .filter(StoredCandidateModel.id.in_(candidate_ids))
            .all()
        )
        return {row.id: row.lemma for row in rows}

    def delete_by_source(self, source_id: int) -> None:
        """Delete all words of a source.

        Their phrases, results, jobs and export records go by DB-level
        ON DELETE CASCADE. Requires PRAGMA foreign_keys = ON (set in database.py).
        """
        models = (
            self._session.query(StoredCandidateModel)
            .filter(StoredCandidateModel.source_id == source_id)
            .all()
        )
        for model in models:
            self._session.delete(model)
        self._session.flush()

    # ── private helpers ────────────────────────────────────────────────

    def _word_of(self, candidate: StoredCandidate) -> StoredCandidateModel | None:
        return self._session.scalars(
            select(StoredCandidateModel).where(
                StoredCandidateModel.source_id == candidate.source_id,
                func.lower(StoredCandidateModel.lemma) == candidate.lemma.lower(),
                StoredCandidateModel.is_phrasal_verb == candidate.is_phrasal_verb,
            )
        ).first()

    def _collects(self, source_id: int) -> bool:
        """A topic or the saved phrases: their phrases are collected, not found in a text."""
        role = self._session.scalar(select(SourceModel.role).where(SourceModel.id == source_id))
        return role in COLLECTING_ROLES

    def _primary_model(self, candidate_id: int) -> PhraseModel | None:
        return self._primary.models([candidate_id]).get(candidate_id)

    def _read(
        self, *where: ColumnElement[bool], join_primary: bool = False,
    ) -> list[StoredCandidate]:
        stmt = select(StoredCandidateModel).where(*where).order_by(StoredCandidateModel.id)
        if join_primary:
            stmt = stmt.join(
                PhraseModel, PhraseModel.id == primary_phrase_id(StoredCandidateModel.id),
            )
        return self._view(list(self._session.scalars(stmt).unique()))

    # TRANSITIONAL(words-phrases): removed in Task 10
    def _view(self, words: list[StoredCandidateModel]) -> list[StoredCandidate]:
        """Words as cards: each seen through its primary phrase, results attached."""
        ids = [w.id for w in words]
        primaries = self._primary.models(ids)
        results = self._results.by_phrase({p.id: word_id for word_id, p in primaries.items()})
        prons = {
            r.candidate_id: r.to_entity()
            for r in self._session.scalars(
                select(CandidatePronunciationModel)
                .where(
                    CandidatePronunciationModel.candidate_id.in_(ids),
                    CandidatePronunciationModel.is_generated(),
                )
            )
        }
        images = {
            r.candidate_id: r.to_entity()
            for r in self._session.scalars(
                select(CandidateMeaningImageModel)
                .where(CandidateMeaningImageModel.candidate_id.in_(ids))
            )
        }
        viewed: list[StoredCandidate] = []
        for word in words:
            primary = primaries.get(word.id)
            if primary is None:
                continue
            entity = word.to_entity(primary, status_of(word, primary))
            made = results[primary.id]
            entity.meaning = made.meaning
            entity.media = made.media
            entity.tts = made.tts
            entity.cloze = made.cloze
            entity.pronunciation = prons.get(word.id)
            entity.meaning_image = images.get(word.id)
            viewed.append(entity)
        return viewed


# TRANSITIONAL(words-phrases): removed in Task 10
def _origin_of(
    candidate: StoredCandidate, *, is_new_word: bool, collects: bool,
) -> OccurrenceOrigin:
    """A collected phrase (topic, saved phrases), an example (no place in the text), the
    analyzer's phrase of a new word, or a phrase the user added to a word that has one."""
    if collects or candidate.origin is not None:
        return OccurrenceOrigin.COLLECTED
    if candidate.phrase_position is None:
        return OccurrenceOrigin.EXAMPLE
    return OccurrenceOrigin.AUTO if is_new_word else OccurrenceOrigin.MANUAL


# TRANSITIONAL(words-phrases): removed in Task 10
def _has_status(status: CandidateStatus) -> list[ColumnElement[bool]]:
    """Conditions on a word joined with its primary phrase (as PhraseModel)."""
    if status is CandidateStatus.SKIP:
        return [PhraseModel.skipped.is_(True)]
    return [StoredCandidateModel.status == status.value, PhraseModel.skipped.is_(False)]


def _required(stored: str) -> Phrase:
    phrase = load_phrase(stored)
    assert phrase is not None
    return phrase

