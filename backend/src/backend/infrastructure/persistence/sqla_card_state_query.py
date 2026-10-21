from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.domain.ports.card_state_query import CardStateQuery
from backend.domain.value_objects.generated_parts import JobState
from backend.domain.value_objects.generation_kind import GenerationKind
from backend.domain.value_objects.generation_tally import GenerationGroup, GenerationTally
from backend.domain.value_objects.ordered_card import OrderedCard
from backend.domain.value_objects.section_tally import SectionTally
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.persistence.card_state_codecs import (
    CARD_NAMES,
    DISTINCT_VALUES_KEPT,
    DONE_COLUMNS,
    JOB_COLUMNS,
    TIMED_COLUMN,
    WORD_KINDS,
    NewCountsByStepCodec,
    SectionsByStepCodec,
    plain_stored_card,
)
from backend.infrastructure.persistence.models import (
    PROJECTION_META_ID,
    CardStateModel,
    CEFRBreakdownModel,
    PhraseModel,
    ProjectionMetaModel,
    StoredCandidateModel,
    cefr_level_of,
    load_position_start,
)
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterator, Mapping, Sequence

    from sqlalchemy.orm import Session

    from backend.domain.value_objects.by_step import SectionsByStep
    from backend.domain.value_objects.card_state_rows import StoredCardState

_CARDS = CardStateModel.__tablename__
_WORDS = StoredCandidateModel.__tablename__
_PHRASES = PhraseModel.__tablename__
_BREAKDOWNS = CEFRBreakdownModel.__tablename__
# The votes `cefr_level_of` reads, in `_cefr_level`'s order.
_VOTES = "b.oxford, b.cambridge, b.cefrpy, b.efllex_distribution, b.kelly"
_META = ProjectionMetaModel.metadata.tables[ProjectionMetaModel.__tablename__]

_KINDS: tuple[GenerationKind, ...] = tuple(DONE_COLUMNS)
_JOB_KINDS: tuple[GenerationKind, ...] = tuple(JOB_COLUMNS)
_PHRASE_KINDS: tuple[GenerationKind, ...] = tuple(k for k in _KINDS if k not in WORD_KINDS)
# The kinds a card may be left out of: a clip needs the phrase's timecodes.
_TIMED_KINDS: frozenset[GenerationKind] = frozenset({GenerationKind.MEDIA})
# In the order of ix_card_states_generation, so a source's rows group unsorted.
_FACTS = ("open_sections", *DONE_COLUMNS.values(), TIMED_COLUMN, *JOB_COLUMNS.values())
_IN_PLAY = "removed = 0 AND wants_generation = 1"
_CARD_IN_PLAY = "cs.removed = 0 AND cs.wants_generation = 1"

# (whether the result is made, a job is on its way, a job is there) → [cards, ready ones]
type _Counted = dict[tuple[bool, bool, bool], list[int]]


@dataclass(frozen=True)
class _Facts:
    """In-play cards alike in their open sections, in what was made for them and in what
    the queue holds for them."""

    open_sections: str
    done: tuple[bool, ...]
    timed: bool
    jobs: tuple[JobState, ...]

    def done_of(self, kind: GenerationKind) -> bool:
        return self.done[_KINDS.index(kind)]

    def job_of(self, kind: GenerationKind) -> JobState:
        return self.jobs[_JOB_KINDS.index(kind)]

    def covers(self, kind: GenerationKind) -> bool:
        return kind not in _TIMED_KINDS or self.timed


@dataclass
class _Word:
    """A word with more than one card in play, read card by card: what was made for it and
    what the queue holds for it are the word's, alike on all its cards."""

    done: bool
    job: JobState
    open_sections: dict[int, str] = field(default_factory=dict)


class SqlaCardStateQuery(CardStateQuery):
    """The screens' reads of card_states: grouped counts read in the order of its covering
    indexes, on the driver's own cursor. Stored sections are compared as whole values, never
    read inside.

    The ✨ counts group the cards in play once, what the queue holds for each card included:
    their cost does not grow with the queue. Only the words with several cards in play are
    read card by card."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def revision(self) -> int:
        revision: int = self._session.execute(
            select(_META.c.revision).where(_META.c.id == PROJECTION_META_ID)
        ).scalar_one()
        return revision

    def section_tallies(self, source_ids: Collection[int]) -> dict[int, SectionTally]:
        counts: dict[int, dict[SectionsByStep, int]] = {}
        for source_id, sections, count in self._each_chunk(
            source_ids,
            f"SELECT source_id, sections, count(*) FROM {_CARDS}"  # noqa: S608 — model names
            " WHERE source_id IN ({marks}) AND removed = 0 GROUP BY source_id, sections",
        ):
            counts.setdefault(source_id, {})[SectionsByStepCodec.decode(sections)] = count
        return {source_id: SectionTally(found) for source_id, found in counts.items()}

    def done_of_sources(self, source_ids: Collection[int]) -> dict[int, bool]:
        return {
            phrase_id: bool(is_done)
            for phrase_id, is_done in self._each_chunk(
                source_ids,
                f"SELECT phrase_id, is_done FROM {_CARDS}"  # noqa: S608 — model names
                " WHERE source_id IN ({marks}) AND removed = 0",
            )
        }

    def done_of_phrases(self, phrase_ids: Collection[int]) -> dict[int, bool]:
        cursor = self._session.connection().connection.cursor()
        found: dict[int, bool] = {}
        try:
            for chunk in chunks(sorted(phrase_ids)):
                cursor.execute(
                    f"SELECT phrase_id, is_done FROM {_CARDS}"  # noqa: S608 — model names
                    f" WHERE phrase_id IN ({', '.join('?' for _ in chunk)}) AND removed = 0",
                    chunk,
                )
                found.update((phrase_id, bool(done)) for phrase_id, done in cursor.fetchall())
        finally:
            cursor.close()
        return found

    def changed_since(self, source_ids: Sequence[int], revision: int) -> list[StoredCardState]:
        return [
            plain_stored_card(values)
            for chunk in chunks(sorted(source_ids))
            for values in self._rows(
                f"SELECT {CARD_NAMES} FROM {_CARDS}"  # noqa: S608 — model names
                f" WHERE source_id IN ({', '.join('?' for _ in chunk)}) AND revision > ?",
                (*chunk, revision),
            )
        ]

    def order_rows(self, source_ids: Sequence[int]) -> list[OrderedCard]:
        return self._ordered(source_ids, "cs.source_id")

    def order_rows_of_words(self, word_ids: Collection[int]) -> list[OrderedCard]:
        return self._ordered(word_ids, "cs.word_id")

    def _ordered(self, ids: Collection[int], column: str) -> list[OrderedCard]:
        """The cards whose `column` is one of `ids`, as the review order reads them."""
        return [
            OrderedCard(
                phrase_id=phrase_id,
                word_id=word_id,
                source_id=source_id,
                lemma=lemma,
                pos=pos,
                zipf_frequency=zipf,
                cefr_level=_cefr_level(*votes) if has_breakdown else None,
                occurrences=occurrences,
                is_phrasal_verb=bool(phrasal),
                usage_distribution=_usage(usage),
                place=load_position_start(position),
                is_done=bool(is_done),
                sections=SectionsByStepCodec.decode(sections),
                new_counts=NewCountsByStepCodec.decode(new_counts),
            )
            for (
                phrase_id, word_id, source_id, lemma, pos, zipf, occurrences, phrasal, usage,
                position, is_done, sections, new_counts, has_breakdown, *votes,
            ) in self._each_chunk(
                ids,
                "SELECT cs.phrase_id, cs.word_id, cs.source_id, c.lemma, c.pos,"  # noqa: S608 — model names
                " c.zipf_frequency, c.occurrences, c.is_phrasal_verb, c.usage_distribution,"
                " p.phrase_position, cs.is_done, cs.sections, cs.new_counts, b.id IS NOT NULL,"
                f" {_VOTES} FROM {_CARDS} cs JOIN {_WORDS} c ON c.id = cs.word_id"
                f" JOIN {_PHRASES} p ON p.id = cs.phrase_id"
                f" LEFT JOIN {_BREAKDOWNS} b ON b.candidate_id = cs.word_id"
                f" WHERE {column} IN ({{marks}}) AND cs.removed = 0",
            )
        ]

    def generation_tallies(
        self, source_ids: Collection[int], ready: Callable[[SectionsByStep], bool],
    ) -> dict[int, GenerationTally]:
        cards = self._cards(source_ids)
        ready_values = {
            facts.open_sections
            for found in cards.values() for facts in found
            if ready(SectionsByStepCodec.decode(facts.open_sections))
        }
        words = self._words(source_ids)
        tallies: dict[int, GenerationTally] = {}
        for source_id, found in cards.items():
            groups = {
                kind: _groups(_phrase_counted(kind, found, ready_values))
                for kind in _PHRASE_KINDS
            }
            for kind in WORD_KINDS:
                groups[kind] = _groups(_word_counted(
                    kind, found, words.get((source_id, kind), {}), ready_values,
                ))
            tallies[source_id] = GenerationTally(
                {kind: of_kind for kind, of_kind in groups.items() if of_kind},
            )
        return tallies

    # --- the cards in play ------------------------------------------------------------------

    def _cards(self, source_ids: Collection[int]) -> dict[int, dict[_Facts, int]]:
        facts = ", ".join(_FACTS)
        found: dict[int, dict[_Facts, int]] = {}
        for source_id, *values, count in self._each_chunk(
            source_ids,
            f"SELECT source_id, {facts}, count(*) FROM {_CARDS}"  # noqa: S608 — model names
            f" WHERE source_id IN ({{marks}}) AND {_IN_PLAY} GROUP BY source_id, {facts}",
        ):
            of_source = found.setdefault(source_id, {})
            card = _facts(values)
            of_source[card] = of_source.get(card, 0) + count
        return found

    def _words(
        self, source_ids: Collection[int],
    ) -> dict[tuple[int, GenerationKind], dict[int, _Word]]:
        """The words with more than one card in play, read card by card, by source and kind
        of a word."""
        found: dict[tuple[int, GenerationKind], dict[int, _Word]] = {}
        for kind in WORD_KINDS:
            done, job = DONE_COLUMNS[kind], JOB_COLUMNS[kind]
            for source_id, word_id, phrase_id, is_done, state, open_sections in self._each_chunk(
                source_ids,
                f"SELECT cs.source_id, cs.word_id, cs.phrase_id, cs.{done}, cs.{job},"  # noqa: S608 — model names
                f" cs.open_sections FROM {_CARDS} cs JOIN (SELECT word_id FROM {_CARDS}"
                f" WHERE source_id IN ({{marks}}) AND {_IN_PLAY}"
                " GROUP BY source_id, word_id HAVING count(*) > 1) m"
                f" ON m.word_id = cs.word_id WHERE {_CARD_IN_PLAY}",
            ):
                word = found.setdefault((source_id, kind), {}).setdefault(
                    word_id, _Word(bool(is_done), JobState(state)),
                )
                word.open_sections[phrase_id] = open_sections
        return found

    # --- reading ------------------------------------------------------------------------------

    # Any: the driver's rows are untyped; each caller reads its values into typed ones.
    def _rows(self, sql: str, parameters: Sequence[object]) -> list[tuple[Any, ...]]:
        cursor = self._session.connection().connection.cursor()
        try:
            cursor.execute(sql, parameters)
            return list(cursor.fetchall())
        finally:
            cursor.close()

    # Any: the driver's rows are untyped; each caller reads its values into typed ones.
    def _each_chunk(self, source_ids: Collection[int], sql: str) -> Iterator[tuple[Any, ...]]:
        """The rows of `sql` over every chunk of the sources, its `{marks}` the chunk's
        placeholders."""
        cursor = self._session.connection().connection.cursor()
        try:
            for chunk in chunks(sorted(source_ids)):
                cursor.execute(sql.format(marks=", ".join("?" for _ in chunk)), chunk)
                yield from cursor.fetchall()
        finally:
            cursor.close()


@lru_cache(maxsize=DISTINCT_VALUES_KEPT)
def _cefr_level(
    oxford: str | None,
    cambridge: str | None,
    cefrpy: str | None,
    efllex_distribution: str | None,
    kelly: str | None,
) -> str | None:
    """The level of a word with this stored breakdown: a book's words share a few thousand."""
    return cefr_level_of(CEFRBreakdownModel(
        oxford=oxford, cambridge=cambridge, cefrpy=cefrpy,
        efllex_distribution=efllex_distribution, kelly=kelly,
    ))


@lru_cache(maxsize=DISTINCT_VALUES_KEPT)
def _usage(stored: str | None) -> UsageDistribution | None:
    """A word's stored usage groups: a book's words share about a hundred."""
    return UsageDistribution(json.loads(stored)) if stored is not None else None


def _facts(values: Sequence[Any]) -> _Facts:
    """`values`: _FACTS in order."""
    open_sections, *rest = values
    kinds = len(_KINDS)
    return _Facts(
        open_sections,
        tuple(bool(value) for value in rest[:kinds]),
        bool(rest[kinds]),
        tuple(JobState(value) for value in rest[kinds + 1:]),
    )


def _key(done: bool, job: JobState) -> tuple[bool, bool, bool]:
    """The group of cards alike for a kind: made, a job on its way, a job there."""
    return done, job is JobState.ACTIVE, job is not JobState.NONE


def _add(counted: _Counted, key: tuple[bool, bool, bool], cards: int, ready: int) -> None:
    if cards:
        totals = counted.setdefault(key, [0, 0])
        totals[0] += cards
        totals[1] += ready


def _groups(counted: _Counted) -> tuple[GenerationGroup, ...]:
    return tuple(
        GenerationGroup(
            done=done, active_job=active, failed_job=has_job, cards=cards, ready=ready,
        )
        for (done, active, has_job), (cards, ready) in counted.items()
    )


def _phrase_counted(
    kind: GenerationKind, cards: Mapping[_Facts, int], ready_values: set[str],
) -> _Counted:
    """The covered cards of one source for a kind of a phrase, by what was made for them
    and what the queue holds for them. Plain dicts: a book counts each kind of its hundreds
    of sources."""
    counted: _Counted = {}
    for facts, count in cards.items():
        if facts.covers(kind):
            ready = count * (facts.open_sections in ready_values)
            _add(counted, _key(facts.done_of(kind), facts.job_of(kind)), count, ready)
    return counted


def _word_counted(
    kind: GenerationKind,
    cards: Mapping[_Facts, int],
    words: Mapping[int, _Word],
    ready_values: set[str],
) -> _Counted:
    """The words of one source with a card in play, for a kind of a word: a word with
    several cards in play counts once and wants ready generation when one of its cards
    does; every other word has one card in play and counts as that card."""
    counted: _Counted = {}
    plain: dict[tuple[str, bool, JobState], int] = {}
    for facts, count in cards.items():
        key = (facts.open_sections, facts.done_of(kind), facts.job_of(kind))
        plain[key] = plain.get(key, 0) + count
    for word in words.values():
        for open_sections in word.open_sections.values():
            plain[(open_sections, word.done, word.job)] -= 1
        ready = any(value in ready_values for value in word.open_sections.values())
        _add(counted, _key(word.done, word.job), 1, int(ready))
    for (open_sections, done, job), count in plain.items():
        _add(counted, _key(done, job), count, count * (open_sections in ready_values))
    return counted
