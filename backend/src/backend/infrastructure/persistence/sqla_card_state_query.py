from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.domain.ports.card_state_query import CardStateQuery
from backend.domain.value_objects.generation_kind import GenerationKind
from backend.domain.value_objects.generation_tally import GenerationGroup, GenerationTally
from backend.domain.value_objects.section_tally import SectionTally
from backend.infrastructure.persistence.card_state_codecs import (
    DONE_COLUMNS,
    TIMED_COLUMN,
    SectionsByStepCodec,
)
from backend.infrastructure.persistence.models import (
    PROJECTION_META_ID,
    CardStateModel,
    JobModel,
    ProjectionMetaModel,
)
from backend.infrastructure.persistence.phrase_writes import chunks
from backend.infrastructure.persistence.sqla_occurrence_repository import ACTIVE_JOB_STATUSES

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence

    from sqlalchemy.orm import Session

    from backend.domain.value_objects.by_step import SectionsByStep

_CARDS = CardStateModel.__tablename__
_JOBS = JobModel.__tablename__
_META = ProjectionMetaModel.metadata.tables[ProjectionMetaModel.__tablename__]

_KINDS: tuple[GenerationKind, ...] = tuple(DONE_COLUMNS)
# The kinds made once per word; every other kind is made for each card.
_WORD_KINDS: tuple[GenerationKind, ...] = (GenerationKind.PRONUNCIATION,)
_PHRASE_KINDS: tuple[GenerationKind, ...] = tuple(k for k in _KINDS if k not in _WORD_KINDS)
# The kinds a card may be left out of: a clip needs the phrase's timecodes.
_TIMED_KINDS: frozenset[GenerationKind] = frozenset({GenerationKind.MEDIA})
# In the order of ix_card_states_generation, so a source's rows group unsorted.
_FACTS = ("open_sections", *DONE_COLUMNS.values(), TIMED_COLUMN)
_IN_PLAY = "removed = 0 AND wants_generation = 1"
_CARD_IN_PLAY = "cs.removed = 0 AND cs.wants_generation = 1"
_ACTIVE = ", ".join(f"'{status}'" for status in ACTIVE_JOB_STATUSES)

# (whether the result is made, a job is on its way, a job is there) → [cards, ready ones]
type _Counted = dict[tuple[bool, bool, bool], list[int]]


@dataclass(frozen=True)
class _Facts:
    """In-play cards alike in their open sections and in what was made for them."""

    open_sections: str
    done: tuple[bool, ...]
    timed: bool

    def done_of(self, kind: GenerationKind) -> bool:
        return self.done[_KINDS.index(kind)]

    def covers(self, kind: GenerationKind) -> bool:
        return kind not in _TIMED_KINDS or self.timed


@dataclass
class _Word:
    """A word read card by card: one with more than one card in play, or with a job."""

    done: bool
    open_sections: dict[int, str] = field(default_factory=dict)
    active_job: bool = False
    has_job: bool = False


class SqlaCardStateQuery(CardStateQuery):
    """The screens' reads of card_states: grouped counts read in the order of its covering
    indexes, on the driver's own cursor. Stored sections are compared as whole values, never
    read inside.

    The ✨ counts group the cards in play once; the jobs, and the words read card by card,
    are read from their own side: their cost grows with the queue, not with the book."""

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

    def generation_tallies(
        self, source_ids: Collection[int], ready: Callable[[SectionsByStep], bool],
    ) -> dict[int, GenerationTally]:
        cards = self._cards(source_ids)
        ready_values = {
            facts.open_sections
            for found in cards.values() for facts in found
            if ready(SectionsByStepCodec.decode(facts.open_sections))
        }
        jobs = self._phrase_jobs(source_ids)
        words = self._words(source_ids)
        tallies: dict[int, GenerationTally] = {}
        for source_id, found in cards.items():
            groups = {
                kind: _groups(_phrase_counted(
                    kind, found, jobs.get((source_id, kind), {}), ready_values,
                ))
                for kind in _PHRASE_KINDS
            }
            for kind in _WORD_KINDS:
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

    def _phrase_jobs(
        self, source_ids: Collection[int],
    ) -> dict[tuple[int, GenerationKind], dict[tuple[_Facts, bool], int]]:
        """In-play cards with a job of a kind of a phrase, by source and kind: their facts
        and whether one of their jobs is on its way."""
        facts = ", ".join(f"cs.{name}" for name in _FACTS)
        kinds = ", ".join(f"'{kind.job_type.value}'" for kind in _PHRASE_KINDS)
        found: dict[tuple[int, GenerationKind], dict[tuple[_Facts, bool], int]] = {}
        for source_id, job_type, active, *values, count in self._each_chunk(
            source_ids,
            f"SELECT cs.source_id, j.job_type, j.active, {facts}, count(*)"  # noqa: S608 — model names
            f" FROM (SELECT phrase_id, job_type, max(status IN ({_ACTIVE})) AS active"
            f" FROM {_JOBS} WHERE phrase_id IS NOT NULL AND job_type IN ({kinds})"
            " GROUP BY phrase_id, job_type) j"
            f" JOIN {_CARDS} cs ON cs.phrase_id = j.phrase_id"
            f" WHERE cs.source_id IN ({{marks}}) AND {_CARD_IN_PLAY}"
            f" GROUP BY cs.source_id, j.job_type, j.active, {facts}",
        ):
            of_kind = found.setdefault((source_id, GenerationKind(job_type)), {})
            card = (_facts(values), bool(active))
            of_kind[card] = of_kind.get(card, 0) + count
        return found

    def _words(
        self, source_ids: Collection[int],
    ) -> dict[tuple[int, GenerationKind], dict[int, _Word]]:
        """The words of a kind of a word to read card by card, by source and kind: those
        with more than one card in play, and those with a job of the kind."""
        found: dict[tuple[int, GenerationKind], dict[int, _Word]] = {}
        for kind in _WORD_KINDS:
            done = DONE_COLUMNS[kind]
            several: Iterable[tuple[Any, ...]] = (
                (*row, False, False) for row in self._each_chunk(
                    source_ids,
                    f"SELECT cs.source_id, cs.word_id, cs.phrase_id, cs.{done}, cs.open_sections"  # noqa: S608 — model names
                    f" FROM {_CARDS} cs JOIN (SELECT word_id FROM {_CARDS}"
                    f" WHERE source_id IN ({{marks}}) AND {_IN_PLAY}"
                    " GROUP BY source_id, word_id HAVING count(*) > 1) m"
                    f" ON m.word_id = cs.word_id WHERE {_CARD_IN_PLAY}",
                )
            )
            with_jobs = self._each_chunk(
                source_ids,
                f"SELECT cs.source_id, cs.word_id, cs.phrase_id, cs.{done}, cs.open_sections,"  # noqa: S608 — model names
                f" j.active, 1 FROM (SELECT candidate_id, max(status IN ({_ACTIVE})) AS active"
                f" FROM {_JOBS} WHERE candidate_id IS NOT NULL"
                f" AND job_type = '{kind.job_type.value}' GROUP BY candidate_id) j"
                f" JOIN {_CARDS} cs ON cs.word_id = j.candidate_id"
                f" WHERE cs.source_id IN ({{marks}}) AND {_CARD_IN_PLAY}",
            )
            for rows in (several, with_jobs):
                for source_id, word_id, phrase_id, is_done, open_sections, active, job in rows:
                    word = found.setdefault((source_id, kind), {}).setdefault(
                        word_id, _Word(bool(is_done)),
                    )
                    word.open_sections[phrase_id] = open_sections
                    word.active_job = word.active_job or bool(active)
                    word.has_job = word.has_job or bool(job)
        return found

    # --- reading ------------------------------------------------------------------------------

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


def _facts(values: Sequence[Any]) -> _Facts:
    """`values`: _FACTS in order."""
    open_sections, *done, timed = values
    return _Facts(open_sections, tuple(bool(value) for value in done), bool(timed))


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
    kind: GenerationKind,
    cards: Mapping[_Facts, int],
    jobs: Mapping[tuple[_Facts, bool], int],
    ready_values: set[str],
) -> _Counted:
    """The covered cards of one source for a kind of a phrase: those with a job of the kind
    as their jobs say, the rest without one. A card's job of the kind, when it has one, is
    active or else failed. Plain dicts: a book counts each kind of its hundreds of sources."""
    counted: _Counted = {}
    with_job: dict[_Facts, int] = {}
    for (facts, active), count in jobs.items():
        with_job[facts] = with_job.get(facts, 0) + count
        if facts.covers(kind):
            ready = count * (facts.open_sections in ready_values)
            _add(counted, (facts.done_of(kind), active, True), count, ready)
    for facts, count in cards.items():
        if facts.covers(kind):
            plain = count - with_job.get(facts, 0)
            ready = plain * (facts.open_sections in ready_values)
            _add(counted, (facts.done_of(kind), False, False), plain, ready)
    return counted


def _word_counted(
    kind: GenerationKind,
    cards: Mapping[_Facts, int],
    words: Mapping[int, _Word],
    ready_values: set[str],
) -> _Counted:
    """The words of one source with a card in play, for a kind of a word: a word read card
    by card wants ready generation when one of its cards does; every other word has one
    card in play and no job, and counts as that card."""
    counted: _Counted = {}
    plain: dict[tuple[str, bool], int] = {}
    for facts, count in cards.items():
        key = (facts.open_sections, facts.done_of(kind))
        plain[key] = plain.get(key, 0) + count
    for word in words.values():
        for open_sections in word.open_sections.values():
            plain[(open_sections, word.done)] -= 1
        ready = any(value in ready_values for value in word.open_sections.values())
        _add(counted, (word.done, word.active_job, word.has_job), 1, int(ready))
    for (open_sections, done), count in plain.items():
        _add(counted, (done, False, False), count, count * (open_sections in ready_values))
    return counted
