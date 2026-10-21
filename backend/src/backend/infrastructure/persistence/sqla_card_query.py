from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from backend.domain.ports.card_query import CardQuery
from backend.domain.value_objects.review_card import CardRow, CardTargetRow
from backend.domain.value_objects.shown_place import ShownPlace
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.card_state_codecs import (
    GENERATED_COLUMNS,
    GeneratedPartsCodec,
)
from backend.infrastructure.persistence.models import (
    WORD_DECISION_STATUS,
    CandidateMeaningModel,
    CandidateMediaModel,
    CandidatePronunciationModel,
    CandidateTTSModel,
    CEFRBreakdownModel,
    PhraseModel,
    StoredCandidateModel,
    WordStateModel,
    cefr_level_of,
    earned_section_of,
    load_phrase,
    load_position,
)
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from sqlalchemy import ColumnElement, Select
    from sqlalchemy.orm import Session

    from backend.domain.value_objects.generated_parts import GeneratedParts
    from backend.domain.value_objects.phrase import Phrase


class SqlaCardQuery(CardQuery):
    """SQLAlchemy implementation of CardQuery: one query over phrases joined with words."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def shown_cards(self, source_ids: list[int]) -> dict[int, list[CardRow]]:
        found: dict[int, list[CardRow]] = {}
        for chunk in chunks(source_ids):
            for card in self._cards(StoredCandidateModel.source_id.in_(chunk)):
                found.setdefault(card.source_id, []).append(card)
        return found

    def shown_cards_of_phrases(self, phrase_ids: Collection[int]) -> list[CardRow]:
        return [
            card for chunk in chunks(sorted(phrase_ids))
            for card in self._cards(PhraseModel.id.in_(chunk))
        ]

    def shown_cards_of_words(self, word_ids: Collection[int]) -> list[CardRow]:
        return [
            card for chunk in chunks(sorted(word_ids))
            for card in self._cards(StoredCandidateModel.id.in_(chunk))
        ]

    def card_targets(self, phrase_ids: Collection[int]) -> list[CardTargetRow]:
        return [
            card for chunk in chunks(sorted(phrase_ids))
            for card in self._targets(PhraseModel.id.in_(chunk))
        ]

    def card_targets_of_words(self, word_ids: Collection[int]) -> list[CardTargetRow]:
        return [
            card for chunk in chunks(sorted(word_ids))
            for card in self._targets(StoredCandidateModel.id.in_(chunk))
        ]

    def generated_parts(self, phrase_ids: Collection[int]) -> dict[int, GeneratedParts]:
        found: dict[int, GeneratedParts] = {}
        for chunk in chunks(sorted(phrase_ids)):
            rows = self._session.execute(
                _with_generated(
                    select(PhraseModel.id, *_GENERATED_COLUMNS)
                    .join(
                        StoredCandidateModel,
                        StoredCandidateModel.id == PhraseModel.candidate_id,
                    )
                    .where(PhraseModel.id.in_(chunk), PhraseModel.shown_by.is_not(None)),
                ),
            ).all()
            found.update(
                {phrase_id: GeneratedPartsCodec.decode(facts) for phrase_id, *facts in rows},
            )
        return found

    def _cards(self, where: ColumnElement[bool]) -> list[CardRow]:
        rows = self._session.execute(
            _with_generated(
                select(
                    StoredCandidateModel.source_id,
                    StoredCandidateModel.id,
                    StoredCandidateModel.lemma,
                    StoredCandidateModel.pos,
                    StoredCandidateModel.zipf_frequency,
                    WORD_DECISION_STATUS,
                    PhraseModel.id,
                    PhraseModel.is_skipped(),
                    PhraseModel.source_phrase,
                    PhraseModel.polished_phrase,
                    PhraseModel.polish_reverted,
                    PhraseModel.earned_section,
                    *_GENERATED_COLUMNS,
                )
                .join(PhraseModel, PhraseModel.candidate_id == StoredCandidateModel.id)
                .where(where, PhraseModel.shown_by.is_not(None))
                .order_by(PhraseModel.id),
            ),
        ).all()
        return [
            CardRow(
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
                earned_section=earned_section_of(earned, phrase_id),
                generated=GeneratedPartsCodec.decode(generated),
            )
            for (
                source_id, word_id, lemma, pos, zipf, status, phrase_id, skipped,
                source_phrase, polished, reverted, earned, *generated,
            ) in rows
        ]

    def _targets(self, where: ColumnElement[bool]) -> list[CardTargetRow]:
        rows = self._session.execute(
            select(
                StoredCandidateModel.source_id,
                StoredCandidateModel.id,
                StoredCandidateModel.lemma,
                StoredCandidateModel.pos,
                StoredCandidateModel.zipf_frequency,
                PhraseModel.id,
                PhraseModel.earned_section,
            )
            .join(PhraseModel, PhraseModel.candidate_id == StoredCandidateModel.id)
            .where(where, PhraseModel.shown_by.is_not(None))
            .order_by(PhraseModel.id)
        ).all()
        return [
            CardTargetRow(
                source_id=source_id,
                word_id=word_id,
                phrase_id=phrase_id,
                lemma=lemma,
                pos=pos,
                zipf_frequency=zipf,
                earned_section=earned_section_of(earned, phrase_id),
            )
            for source_id, word_id, lemma, pos, zipf, phrase_id, earned in rows
        ]

    def learn_counts(self, source_ids: list[int]) -> dict[int, int]:
        counts: dict[int, int] = {}
        for chunk in chunks(source_ids):
            rows = self._session.execute(
                select(WordStateModel.source_id, func.count(WordStateModel.word_id))
                .where(WordStateModel.source_id.in_(chunk), WordStateModel.chosen_to_learn())
                .group_by(WordStateModel.source_id)
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


# What generation made for a shown phrase, as `GenerationTarget.is_done` and `covers` read
# it from the loaded entities, in GENERATED_COLUMNS order.
_GENERATED: Mapping[str, ColumnElement[bool]] = MappingProxyType({
    "polish_done": PhraseModel.polished_phrase.is_not(None),
    "meaning_done": CandidateMeaningModel.meaning.is_not(None),
    "media_done": CandidateMediaModel.screenshot_path.is_not(None),
    "tts_done": CandidateTTSModel.audio_path.is_not(None),
    "pronunciation_done": (
        CandidatePronunciationModel.candidate_id.is_not(None)
        & CandidatePronunciationModel.is_generated()
    ),
    "media_timed": (
        CandidateMediaModel.start_ms.is_not(None) & CandidateMediaModel.end_ms.is_not(None)
    ),
})
_GENERATED_COLUMNS = tuple(_GENERATED[name] for name in GENERATED_COLUMNS)


# Any: each caller selects its own columns; the joins are the same for all of them.
def _with_generated[T: Select[Any]](query: T) -> T:
    """The query over phrases and their words, joined with what was made for them."""
    return (
        query
        .outerjoin(CandidateMeaningModel, CandidateMeaningModel.phrase_id == PhraseModel.id)
        .outerjoin(CandidateMediaModel, CandidateMediaModel.phrase_id == PhraseModel.id)
        .outerjoin(CandidateTTSModel, CandidateTTSModel.phrase_id == PhraseModel.id)
        .outerjoin(
            CandidatePronunciationModel,
            CandidatePronunciationModel.candidate_id == StoredCandidateModel.id,
        )
    )


def _required(stored: str) -> Phrase:
    phrase = load_phrase(stored)
    assert phrase is not None
    return phrase
