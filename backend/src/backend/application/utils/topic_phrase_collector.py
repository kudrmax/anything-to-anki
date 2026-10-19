from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.exceptions import TargetNotInPhraseError
from backend.domain.services.card_view import is_skipped
from backend.domain.services.topic_phrase_selection import (
    find_shortest_sentence,
    parse_marked_phrase,
    pick_easiest_phrase,
)
from backend.domain.value_objects.document import block_text
from backend.domain.value_objects.phrase_origin import PhraseOrigin, PhraseOriginKind

if TYPE_CHECKING:
    from backend.application.utils.candidate_factory import CandidateFactory
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.application.utils.user_knowledge_reader import UserKnowledgeReader
    from backend.domain.entities.source import Source
    from backend.domain.entities.topic_target import TopicTarget
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.topic_target_repository import TopicTargetRepository
    from backend.domain.value_objects.document import Document
    from backend.domain.value_objects.new_card import NewCard
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.user_knowledge import UserKnowledge

logger = logging.getLogger(__name__)

SINGLE_OCCURRENCE = 1


@dataclass(frozen=True)
class _Found:
    phrase: Phrase
    origin: PhraseOrigin


class TopicPhraseCollector:
    """Turns the targets of a topic into cards. Mechanical, no AI.

    For every target it looks for a real phrase among the sources the user has
    added: first a phrase shown for the same lemma in a source, then any sentence of
    their documents that contains the target verbatim. Only when neither exists does
    the card keep the example AI generated.
    """

    def __init__(
        self,
        topic_target_repo: TopicTargetRepository,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        candidate_repo: CandidateRepository,
        occurrence_repo: OccurrenceRepository,
        knowledge: UserKnowledgeReader,
        candidate_factory: CandidateFactory,
        phrase_reader: PhraseReader,
    ) -> None:
        self._topic_target_repo = topic_target_repo
        self._source_repo = source_repo
        self._document_repo = document_repo
        self._candidate_repo = candidate_repo
        self._occurrence_repo = occurrence_repo
        self._knowledge = knowledge
        self._candidate_factory = candidate_factory
        self._phrase_reader = phrase_reader

    def has_targets(self, source_id: int) -> bool:
        return self._topic_target_repo.has_targets(source_id)

    def collect(self, source_id: int) -> list[NewCard]:
        targets = self._topic_target_repo.get_by_source(source_id)
        knowledge = self._knowledge.current()
        library = {
            s.id: (s, document) for s in self._source_repo.list_all()
            if s.id is not None and (document := self._document_repo.get(s.id)) is not None
        }

        cards: list[NewCard] = []
        seen: set[str] = set()
        for target in targets:
            generated = self._generated_card(source_id, target)
            if generated is None:
                continue
            lemma = generated.word.lemma
            if lemma in seen or knowledge.vocabulary.is_known_or_learning(lemma):
                continue
            seen.add(lemma)
            found = self._real_phrase(generated, target, library, knowledge)
            cards.append(
                generated if found is None else self._candidate_factory.build(
                    source_id=source_id,
                    phrase=found.phrase,
                    occurrences=SINGLE_OCCURRENCE,
                    origin=found.origin,
                ),
            )

        borrowed = sum(
            1 for c in cards if c.origin and c.origin.kind == PhraseOriginKind.SOURCE
        )
        logger.info(
            "topic_phrase_collector: done (source_id=%d, targets=%d, candidates=%d, "
            "from_sources=%d)",
            source_id, len(targets), len(cards), borrowed,
        )
        return cards

    def _generated_card(self, source_id: int, target: TopicTarget) -> NewCard | None:
        example = parse_marked_phrase(target.example)
        if example is None:
            logger.warning(
                "topic_phrase_collector: example without marked target (target_id=%s)",
                target.id,
            )
            return None
        try:
            phrase = self._phrase_reader.read(example.text, example.spans)
        except TargetNotInPhraseError:
            phrase = None
        if phrase is None:
            logger.warning(
                "topic_phrase_collector: marked target not among the words (target_id=%s)",
                target.id,
            )
            return None
        return self._candidate_factory.build(
            source_id=source_id,
            phrase=phrase,
            occurrences=SINGLE_OCCURRENCE,
            origin=PhraseOrigin.generated(),
        )

    def _real_phrase(
        self,
        generated: NewCard,
        target: TopicTarget,
        library: dict[int, tuple[Source, Document]],
        knowledge: UserKnowledge,
    ) -> _Found | None:
        sources = {
            word.id: word.source_id
            for word in self._candidate_repo.get_by_lemma(generated.word.lemma)
            if word.id is not None and word.source_id in library
        }
        shown = [
            occ for word_id in sources for occ in self._occurrence_repo.of_word(word_id)
            if occ.is_shown and not is_skipped(occ.card_state)
        ]
        best = pick_easiest_phrase(shown, knowledge)
        if best is not None:
            return _Found(
                phrase=best.source_phrase,
                origin=PhraseOrigin.from_source(
                    _title(library[sources[best.candidate_id]][0]),
                ),
            )

        variants = {target.phrase, generated.phrase.target_text()}
        # A sentence never runs across blocks: a heading or a list item stands alone.
        found = [
            (sentence, source)
            for source, document in library.values()
            for block in document.blocks
            if (sentence := find_shortest_sentence(block_text(block), variants))
        ]
        if not found:
            return None
        sentence, source = min(found, key=lambda pair: len(pair[0].text.split()))
        phrase = self._phrase(sentence.text, sentence.target)
        if phrase is None:
            return None
        return _Found(phrase=phrase, origin=PhraseOrigin.from_source(_title(source)))

    def _phrase(self, text: str, target: str) -> Phrase | None:
        try:
            return self._phrase_reader.read_for(text, target)
        except TargetNotInPhraseError:
            return None


def _title(source: Source) -> str:
    return source.title or ""
