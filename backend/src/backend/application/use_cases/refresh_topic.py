from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.rebuild_dtos import TopicRefreshSummaryDTO
from backend.domain.exceptions import (
    RefreshNotSupportedError,
    SourceNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.services.phrase_protection import has_user_work
from backend.domain.services.rebuild_plan import RebuildPlan
from backend.domain.services.source_operations import available_operation
from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.phrase_origin import PhraseOriginKind
from backend.domain.value_objects.source_operation_kind import SourceOperationKind

if TYPE_CHECKING:
    from backend.application.utils.collected_phrases import CollectedPhrases
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.application.utils.topic_phrase_collector import TopicPhraseCollector
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.new_card import NewCard
    from backend.domain.value_objects.word_row import WordRow

logger = logging.getLogger(__name__)


class RefreshTopicUseCase:
    """Collects a topic's phrases again and adds only what it has not got yet.

    Sources added since the topic was processed may hold real phrases for its targets.
    A real phrase replaces a generated example nobody worked with; otherwise it is added
    beside it. Decisions, results and every phrase the user worked with stay as they are.
    `start` takes the source and must be committed before `run`, which frees it whatever
    happens.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        occurrence_repo: OccurrenceRepository,
        collected_phrases: CollectedPhrases,
        lock: SourceOperationLock,
        unit_of_work: UnitOfWork,
        collector: TopicPhraseCollector,
        review_status: ReviewStatusUpdater,
    ) -> None:
        self._source_repo = source_repo
        self._occurrence_repo = occurrence_repo
        self._collected_phrases = collected_phrases
        self._lock = lock
        self._unit_of_work = unit_of_work
        self._collector = collector
        self._review_status = review_status

    def start(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if available_operation(source) is not SourceOperationKind.REFRESH:
            raise RefreshNotSupportedError(source_id)
        if not self._lock.acquire(source_id, SourceOperationKind.REFRESH):
            raise SourceOperationBusyError(source_id, self._lock.held(source_id))

    def execute(self, source_id: int) -> TopicRefreshSummaryDTO:
        self.start(source_id)
        self._unit_of_work.commit()
        return self.run(source_id)

    def run(self, source_id: int) -> TopicRefreshSummaryDTO:
        try:
            self._unit_of_work.commit()
            collected = self._collector.collect(source_id)
            with self._unit_of_work.write():
                if self._source_repo.get_by_id(source_id) is None:
                    raise SourceNotFoundError(source_id)
                summary = self._add_missing(source_id, collected)
                self._review_status.refresh(source_id)
            logger.info(
                "refresh_topic: done (source_id=%d, words_added=%d, phrases_added=%d)",
                source_id, summary.words_added, summary.phrases_added,
            )
            return summary
        finally:
            self._unit_of_work.rollback()
            self._lock.release(source_id)
            self._unit_of_work.commit()

    def _add_missing(self, source_id: int, collected: list[NewCard]) -> TopicRefreshSummaryDTO:
        words = {w.key: w for w in self._occurrence_repo.word_rows(source_id)}
        rows: dict[int, list[OccurrenceRow]] = {w.id: [] for w in words.values()}
        for row in self._occurrence_repo.projection(source_id):
            rows[row.candidate_id].append(row)
        texts = {key: {r.text_hash for r in rows[w.id]} for key, w in words.items()}
        missing: list[NewCard] = []
        replaced: list[int] = []
        handled: set[int] = set()
        for card in collected:
            key = WordKey.of(card.word.lemma, card.word.is_phrasal_verb)
            text = OccurrenceRow.hash_text(card.phrase.text)
            if text in texts.get(key, set()):
                continue
            texts.setdefault(key, set()).add(text)
            missing.append(card)
            word = words.get(key)
            if word is None or word.id in handled:
                continue
            example = self._generated_example(card, word, rows[word.id])
            if example is not None:
                handled.add(word.id)
                replaced.append(example)
        if replaced:
            self._occurrence_repo.apply_plan(
                RebuildPlan(source_id=source_id, occ_to_delete=tuple(replaced)),
            )
        self._collected_phrases.add(source_id, missing)
        new_words = {WordKey.of(c.word.lemma, c.word.is_phrasal_verb) for c in missing}
        return TopicRefreshSummaryDTO(
            words_added=len(new_words - set(words)),
            phrases_added=len(missing),
            phrases_replaced=len(replaced),
        )

    def _generated_example(
        self, card: NewCard, word: WordRow, phrases: list[OccurrenceRow],
    ) -> int | None:
        """The id of the generated example a real phrase takes the place of, if any.

        Only a word still as processing left it qualifies: its one phrase is the generated
        example and nobody did anything with the word or that phrase. Once a word has a real
        phrase, refreshing only adds to it.
        """
        if (
            card.origin is None
            or card.origin.kind is not PhraseOriginKind.SOURCE
            or word.decided
            or len(phrases) != 1
        ):
            return None
        [example] = phrases
        if has_user_work(example, word.decided):
            return None
        found = self._occurrence_repo.get(example.id)
        generated = (
            found is not None
            and found.collected_from is not None
            and found.collected_from.kind is PhraseOriginKind.GENERATED
        )
        return example.id if generated else None
