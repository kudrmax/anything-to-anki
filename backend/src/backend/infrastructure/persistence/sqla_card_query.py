from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from backend.domain.ports.card_query import CardQuery
from backend.domain.value_objects.review_card import CardRow
from backend.domain.value_objects.shown_place import ShownPlace
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import (
    CEFRBreakdownModel,
    PhraseModel,
    StoredCandidateModel,
    cefr_level_of,
    load_phrase,
    load_position,
)
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.value_objects.phrase import Phrase


class SqlaCardQuery(CardQuery):
    """SQLAlchemy implementation of CardQuery: one query over phrases joined with words."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def shown_cards(self, source_ids: list[int]) -> dict[int, list[CardRow]]:
        found: dict[int, list[CardRow]] = {}
        for chunk in chunks(source_ids):
            rows = self._session.execute(
                select(
                    StoredCandidateModel.source_id,
                    StoredCandidateModel.id,
                    StoredCandidateModel.lemma,
                    StoredCandidateModel.pos,
                    StoredCandidateModel.zipf_frequency,
                    StoredCandidateModel.status,
                    PhraseModel.id,
                    PhraseModel.is_skipped(),
                    PhraseModel.source_phrase,
                    PhraseModel.polished_phrase,
                    PhraseModel.polish_reverted,
                )
                .join(PhraseModel, PhraseModel.candidate_id == StoredCandidateModel.id)
                .where(
                    StoredCandidateModel.source_id.in_(chunk),
                    PhraseModel.shown_by.is_not(None),
                )
                .order_by(PhraseModel.id)
            ).all()
            for (
                source_id, word_id, lemma, pos, zipf, status, phrase_id, skipped,
                source_phrase, polished, reverted,
            ) in rows:
                found.setdefault(source_id, []).append(CardRow(
                    source_id=source_id,
                    word_id=word_id,
                    phrase_id=phrase_id,
                    lemma=lemma,
                    pos=pos,
                    zipf_frequency=zipf,
                    word_status=WordStatus(status),
                    skipped=bool(skipped),
                    phrase=_required(
                        polished if polished is not None and not reverted else source_phrase,
                    ),
                ))
        return found

    def learn_counts(self, source_ids: list[int]) -> dict[int, int]:
        counts: dict[int, int] = {}
        for chunk in chunks(source_ids):
            rows = self._session.execute(
                select(StoredCandidateModel.source_id, func.count(StoredCandidateModel.id))
                .where(
                    StoredCandidateModel.source_id.in_(chunk),
                    StoredCandidateModel.chosen_to_learn(),
                )
                .group_by(StoredCandidateModel.source_id)
            ).all()
            counts.update({source_id: count for source_id, count in rows})
        return counts

    def shown_places(self, source_id: int) -> list[ShownPlace]:
        rows = self._session.execute(
            select(
                PhraseModel.id,
                StoredCandidateModel.id,
                StoredCandidateModel.is_phrasal_verb,
                CEFRBreakdownModel,
                PhraseModel.source_phrase,
                PhraseModel.phrase_position,
            )
            .join(StoredCandidateModel, StoredCandidateModel.id == PhraseModel.candidate_id)
            .outerjoin(
                CEFRBreakdownModel, CEFRBreakdownModel.candidate_id == StoredCandidateModel.id,
            )
            .where(
                StoredCandidateModel.source_id == source_id,
                PhraseModel.shown_by.is_not(None),
                PhraseModel.phrase_position.is_not(None),
            )
            .order_by(PhraseModel.id)
        ).all()
        places: list[ShownPlace] = []
        for phrase_id, word_id, phrasal, breakdown, source_phrase, stored_position in rows:
            position = load_position(stored_position)
            assert position is not None
            places.append(ShownPlace(
                phrase_id=phrase_id, word_id=word_id, cefr_level=cefr_level_of(breakdown),
                is_phrasal_verb=phrasal, source_phrase=_required(source_phrase),
                position=position,
            ))
        return places


def _required(stored: str) -> Phrase:
    phrase = load_phrase(stored)
    assert phrase is not None
    return phrase
