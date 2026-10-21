from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from sqlalchemy import case, func, select

from backend.domain.ports.card_query import CardQuery
from backend.domain.value_objects.generated_parts import JobState
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.review_card import CardRow, CardTargetRow
from backend.domain.value_objects.shown_place import ShownPlace
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.card_state_codecs import (
    DONE_COLUMNS,
    JOB_COLUMNS,
    TIMED_COLUMN,
    WORD_KINDS,
    GeneratedPartsCodec,
)
from backend.infrastructure.persistence.models import (
    WORD_DECISION_STATUS,
    CandidateMeaningModel,
    CandidateMediaModel,
    CandidatePronunciationModel,
    CandidateTTSModel,
    CEFRBreakdownModel,
    JobModel,
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
    from collections.abc import Collection, Mapping, Sequence

    from sqlalchemy import ColumnElement, Select
    from sqlalchemy.orm import Session

    from backend.domain.value_objects.generated_parts import GeneratedParts
    from backend.domain.value_objects.generation_kind import GenerationKind
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
                {phrase_id: _generated(facts) for phrase_id, *facts in rows},
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
                generated=_generated(generated),
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

    def shown_places(self, source_id: int, blocks: range | None = None) -> list[ShownPlace]:
        """With `blocks`, a phrase is picked by the block of its key, where its target
        starts: the block of its place. A phrase without a key is picked by its place."""
        in_blocks: list[ColumnElement[bool]] = [] if blocks is None else [
            PhraseModel.block.is_(None)
            | PhraseModel.block.between(blocks.start, blocks.stop - 1),
        ]
        rows = self._session.execute(
            select(
                PhraseModel.id,
                StoredCandidateModel.id,
                StoredCandidateModel.is_phrasal_verb,
                CEFRBreakdownModel,
                PhraseModel.source_phrase,
                PhraseModel.phrase_position,
                PhraseModel.block,
            )
            .join(StoredCandidateModel, StoredCandidateModel.id == PhraseModel.candidate_id)
            .outerjoin(
                CEFRBreakdownModel, CEFRBreakdownModel.candidate_id == StoredCandidateModel.id,
            )
            .where(
                StoredCandidateModel.source_id == source_id,
                PhraseModel.shown_by.is_not(None),
                PhraseModel.phrase_position.is_not(None),
                *in_blocks,
            )
            .order_by(PhraseModel.id)
        ).all()
        places: list[ShownPlace] = []
        for phrase_id, word_id, phrasal, breakdown, source_phrase, stored_position, key_block in (
            rows
        ):
            position = load_position(stored_position)
            assert position is not None
            if blocks is not None and key_block is None and position.block not in blocks:
                continue
            places.append(ShownPlace(
                phrase_id=phrase_id, word_id=word_id, cefr_level=cefr_level_of(breakdown),
                is_phrasal_verb=phrasal, source_phrase=_required(source_phrase),
                position=position,
            ))
        return places


# What generation made for a shown phrase, as `GenerationTarget.is_done` and `covers` read
# it from the loaded entities, in the order of DONE_COLUMNS, then TIMED_COLUMN.
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
_PHRASE_JOB_KINDS: tuple[GenerationKind, ...] = tuple(
    kind for kind in JOB_COLUMNS if kind not in WORD_KINDS
)
_JOB_STATE = case(
    (JobModel.status.in_((JobStatus.QUEUED.value, JobStatus.RUNNING.value)),
     int(JobState.ACTIVE)),
    else_=int(JobState.FAILED),
)
# A card's job states of several kinds, read in one lookup as the digits of one number.
_STATES = len(JobState)


def _job_states(kinds: Sequence[GenerationKind], of: ColumnElement[bool]) -> ColumnElement[int]:
    """The job state of each kind for the card, as the digit of base _STATES in the kind's
    place: an active job before a failed one, as `GenerationTarget.state` reads them."""
    digits = [
        func.coalesce(
            func.max(case((JobModel.job_type == kind.job_type.value, _JOB_STATE))), 0,
        ) * _STATES ** place
        for place, kind in enumerate(kinds)
    ]
    total = digits[0]
    for digit in digits[1:]:
        total = total + digit
    types = [kind.job_type.value for kind in kinds]
    return select(total).where(of, JobModel.job_type.in_(types)).scalar_subquery()


_GENERATED_COLUMNS: tuple[ColumnElement[Any], ...] = (
    *(_GENERATED[name] for name in (*DONE_COLUMNS.values(), TIMED_COLUMN)),
    _job_states(_PHRASE_JOB_KINDS, JobModel.phrase_id == PhraseModel.id),
    _job_states(WORD_KINDS, JobModel.candidate_id == StoredCandidateModel.id),
)


# Any: the driver's values are untyped; the codec reads each into its own.
def _generated(values: Sequence[Any]) -> GeneratedParts:
    """`values`: _GENERATED_COLUMNS in order."""
    *facts, phrase_jobs, word_jobs = values
    states = {
        **_digits(_PHRASE_JOB_KINDS, phrase_jobs), **_digits(WORD_KINDS, word_jobs),
    }
    return GeneratedPartsCodec.decode((*facts, *(states[kind] for kind in JOB_COLUMNS)))


def _digits(kinds: Sequence[GenerationKind], code: int | None) -> dict[GenerationKind, int]:
    left = code or 0
    found: dict[GenerationKind, int] = {}
    for kind in kinds:
        left, found[kind] = divmod(left, _STATES)
    return found


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
