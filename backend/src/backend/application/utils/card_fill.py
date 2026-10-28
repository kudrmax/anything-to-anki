from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.utils.generation_targets import CardJobs, GenerationCard, target_for
from backend.domain.services.export_readiness import missing_parts
from backend.domain.value_objects.card_fill_skip import CardFillSkip
from backend.domain.value_objects.generation_blocker import GenerationBlocker
from backend.domain.value_objects.generation_kind import GenerationKind
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.missing_card_part import MissingCardPart

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.application.utils.export_queue import ExportCard
    from backend.application.utils.generation_targets import GenerationTarget
    from backend.domain.entities.job import Job
    from backend.domain.entities.source import Source
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository

_SKIP_OF_BLOCKER: Mapping[GenerationBlocker, CardFillSkip] = {
    GenerationBlocker.VIDEO_NOT_DOWNLOADED: CardFillSkip.VIDEO_NOT_DOWNLOADED,
    GenerationBlocker.VIDEO_DOWNLOADING: CardFillSkip.VIDEO_DOWNLOADING,
}
_ACTIVE = frozenset({JobStatus.QUEUED, JobStatus.RUNNING})


@dataclass(frozen=True)
class PartSkip:
    part: MissingCardPart
    reason: CardFillSkip


@dataclass(frozen=True)
class CardFill:
    """What filling in an incomplete card does with each part it lacks: queues it, leaves
    it to the job already making it, or skips it."""

    queued: tuple[MissingCardPart, ...] = ()
    generating: tuple[MissingCardPart, ...] = ()
    skipped: tuple[PartSkip, ...] = ()


@dataclass(frozen=True)
class FillPlan:
    """The fill of every incomplete card, by phrase id, and the jobs that make it."""

    cards: Mapping[int, CardFill]
    jobs: list[Job]

    def of(self, phrase_id: int) -> CardFill:
        return self.cards.get(phrase_id, CardFill())


@dataclass
class _SourceFacts:
    source: Source
    busy: bool
    video_downloading: bool


class CardFillPlanner:
    """Plans the generation of the parts incomplete export cards lack: the meaning, and the
    phrase audio — a clip cut from the video for a video, TTS for anything else. A part
    nothing can make now is skipped with its reason."""

    def __init__(
        self,
        targets: list[GenerationTarget],
        source_repo: SourceRepository,
        job_repo: JobRepository,
        lock: SourceOperationLock,
    ) -> None:
        self._targets = targets
        self._source_repo = source_repo
        self._job_repo = job_repo
        self._lock = lock

    def plan(self, cards: list[ExportCard]) -> FillPlan:
        generation_cards = [GenerationCard(c.word, c.phrase, in_play=True) for c in cards]
        jobs = CardJobs.of(self._job_repo, generation_cards)
        facts: dict[int, _SourceFacts | None] = {}
        fills: dict[int, CardFill] = {}
        queued: list[Job] = []
        for card in generation_cards:
            source_id = card.word.source_id
            if source_id not in facts:
                facts[source_id] = self._facts(source_id)
            source = facts[source_id]
            if source is not None:
                fills[card.phrase_id] = self._fill(card, source, jobs, queued)
        return FillPlan(cards=fills, jobs=queued)

    def _fill(
        self, card: GenerationCard, facts: _SourceFacts, jobs: CardJobs, queued: list[Job],
    ) -> CardFill:
        to_queue: list[MissingCardPart] = []
        generating: list[MissingCardPart] = []
        skipped: list[PartSkip] = []
        for part in missing_parts(card.phrase):
            if part is MissingCardPart.CLOZE:
                skipped.append(PartSkip(part, CardFillSkip.CLOZE_NEEDS_CHOICE))
                continue
            target = target_for(self._targets, _kind_of(part, facts.source), facts.source)
            job = target.job_of(jobs, card)
            if job is not None and job.status in _ACTIVE:
                generating.append(part)
                continue
            reason = self._skip(target, card, facts)
            if reason is not None:
                skipped.append(PartSkip(part, reason))
                continue
            to_queue.append(part)
            queued.append(target.job(card))
        return CardFill(tuple(to_queue), tuple(generating), tuple(skipped))

    @staticmethod
    def _skip(
        target: GenerationTarget, card: GenerationCard, facts: _SourceFacts,
    ) -> CardFillSkip | None:
        if facts.busy:
            return CardFillSkip.SOURCE_BUSY
        blocker = target.blocker(facts.source, facts.video_downloading)
        if blocker is not None:
            return _SKIP_OF_BLOCKER[blocker]
        if not target.covers(card):
            return CardFillSkip.NO_PHRASE_TIME
        return None

    def _facts(self, source_id: int) -> _SourceFacts | None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            return None
        downloading = (
            source.has_video and source.video_path is None
            and self._job_repo.has_active_jobs_for_source(
                source_id, frozenset({JobType.VIDEO_DOWNLOAD}),
            )
        )
        return _SourceFacts(source, self._lock.held(source_id) is not None, downloading)


def _kind_of(part: MissingCardPart, source: Source) -> GenerationKind:
    if part is MissingCardPart.MEANING:
        return GenerationKind.MEANING
    return GenerationKind.MEDIA if source.has_video else GenerationKind.TTS
