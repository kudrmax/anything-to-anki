"""The projection's rows computed the way the review computes card state today: the
reference the stored projection is checked against."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.generation_targets import CardJobs, generated_parts
from backend.domain.services.candidate_sections import new_words, open_section
from backend.domain.services.card_state_rules import changes_at
from backend.domain.services.card_view import section
from backend.domain.value_objects.by_step import NewCountsByStep, SectionsByStep
from backend.domain.value_objects.card_choice import DecisionStatus
from backend.domain.value_objects.card_state_rows import (
    CardStateRow,
    CardStates,
    PhraseWordRow,
    WordStateRow,
)
from backend.domain.value_objects.frequent_word_threshold import (
    THRESHOLD_STEPS,
    FrequentWordThreshold,
)
from backend.domain.value_objects.user_knowledge import KnowledgeBase, UserKnowledge, newness

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.application.utils.generation_targets import GenerationTarget
    from backend.application.utils.review_cards import ReviewCards
    from backend.application.utils.user_knowledge_reader import UserKnowledgeReader
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.review_card import ReviewCard

# A threshold's key names it in the settings; a threshold made for one step needs none.
STEP_THRESHOLD_KEY = "step"


class LiveCardStates:
    """Every row of the projection from the review's own code path: the review cards with
    the request's knowledge snapshot, `card_section`, `open_section` and the card view per
    threshold step, what the generation targets read as made for each card and as held by
    the queue for it, and each word's decision status read from its cards."""

    def __init__(
        self,
        source_repo: SourceRepository,
        review_cards: ReviewCards,
        candidate_repo: CandidateRepository,
        knowledge: UserKnowledgeReader,
        vocabulary: UserVocabulary,
        targets: Sequence[GenerationTarget],
        job_repo: JobRepository,
    ) -> None:
        self._source_repo = source_repo
        self._job_repo = job_repo
        self._review_cards = review_cards
        self._candidate_repo = candidate_repo
        self._knowledge = knowledge
        self._vocabulary = vocabulary
        self._targets = targets

    def compute(self) -> CardStates:
        source_ids = [s.id for s in self._source_repo.list_all() if s.id is not None]
        base = self._knowledge.base()
        steps = _Steps(base)
        cards: list[CardStateRow] = []
        phrase_words: list[PhraseWordRow] = []
        review_cards = self._review_cards.of_sources(source_ids)
        jobs = CardJobs(
            by_phrase=self._job_repo.get_jobs_for_phrases([c.phrase_id for c in review_cards]),
            by_word=self._job_repo.get_jobs_for_candidates(
                sorted({c.word_id for c in review_cards}),
            ),
        )
        for card in review_cards:
            cards.append(self._card_row(card, steps, jobs))
            phrase_words.extend(_phrase_words(card, base))
        words = [
            WordStateRow(
                word_id=word.id, source_id=word.source_id, lemma=word.lemma.lower(),
                status=DecisionStatus(word.status.value),
            )
            for source_id in source_ids
            for word in self._candidate_repo.get_by_source(source_id)
            if word.id is not None
        ]
        return CardStates(tuple(cards), tuple(words), tuple(phrase_words))

    def _card_row(self, card: ReviewCard, steps: _Steps, jobs: CardJobs) -> CardStateRow:
        """`card_section` is `section` of `open_section`: each step's open section is
        computed once."""
        opened = tuple(
            open_section(card, knowledge, threshold) for knowledge, threshold in steps.each
        )
        return CardStateRow(
            phrase_id=card.phrase_id,
            source_id=card.word.source_id,
            word_id=card.word_id,
            lemma=card.lemma.lower(),
            is_done=card.is_done,
            wants_generation=card.view.wants_generation,
            sections=SectionsByStep(tuple(section(card, shown) for shown in opened)),
            open_sections=SectionsByStep(opened),
            new_counts=NewCountsByStep(tuple(
                len(new_words(card.phrase, knowledge)) for knowledge, _ in steps.each
            )),
            generated=generated_parts(self._targets, card.word, card.occurrence, jobs),
            changes_at=changes_at(self._vocabulary.of(card.lemma), self._vocabulary.scope.now),
        )


class _Steps:
    """What the user knows at each threshold step, as the review reads it at that step."""

    def __init__(self, base: KnowledgeBase) -> None:
        self.each: tuple[tuple[UserKnowledge, FrequentWordThreshold], ...] = tuple(
            (
                UserKnowledge(base.vocabulary, base.user_level, step),
                FrequentWordThreshold(STEP_THRESHOLD_KEY, step, ()),
            )
            for step in THRESHOLD_STEPS
        )


def _phrase_words(card: ReviewCard, base: KnowledgeBase) -> list[PhraseWordRow]:
    target = set(card.phrase.target)
    return [
        PhraseWordRow(
            lemma=word.lemma.lower(),
            phrase_lemma=word.lemma,
            phrase_id=card.phrase_id,
            position=position,
            zipf=word.zipf,
            content=word.content,
            level=word.level,
            newness=newness(word, base.vocabulary, base.user_level),
        )
        for position, word in enumerate(card.phrase.words)
        if position not in target
    ]
