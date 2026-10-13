from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.services.topic_phrase_selection import (
    find_shortest_sentence,
    parse_marked_phrase,
    pick_best_candidate_phrase,
)
from backend.domain.value_objects.document import block_text
from backend.domain.value_objects.phrase_origin import PhraseOrigin, PhraseOriginKind

if TYPE_CHECKING:
    from backend.application.utils.candidate_factory import CandidateFactory
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.source import Source
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.entities.topic_target import TopicTarget
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.topic_target_repository import TopicTargetRepository
    from backend.domain.value_objects.document import Document
    from backend.domain.value_objects.vocabulary import Vocabulary

logger = logging.getLogger(__name__)

SINGLE_OCCURRENCE = 1
PHRASE_SEPARATOR = "\n"


@dataclass(frozen=True)
class CollectedTopic:
    """Candidates of a topic and the text they read as, one phrase per line."""

    candidates: list[StoredCandidate]
    text: str


@dataclass(frozen=True)
class _Phrase:
    text: str
    target: str
    origin: PhraseOrigin


class TopicPhraseCollector:
    """Turns the targets of a topic into candidates. Mechanical, no AI.

    For every target it looks for a real phrase among the sources the user has
    added: first a phrase the pipeline already cut out for the same lemma,
    then any sentence of their documents that contains the target verbatim.
    Only when neither exists does the candidate keep the example AI generated.
    """

    def __init__(
        self,
        topic_target_repo: TopicTargetRepository,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        candidate_repo: CandidateRepository,
        vocabulary: UserVocabulary,
        candidate_factory: CandidateFactory,
    ) -> None:
        self._topic_target_repo = topic_target_repo
        self._source_repo = source_repo
        self._document_repo = document_repo
        self._candidate_repo = candidate_repo
        self._vocabulary = vocabulary
        self._candidate_factory = candidate_factory

    def has_targets(self, source_id: int) -> bool:
        return self._topic_target_repo.has_targets(source_id)

    def collect(self, source_id: int) -> CollectedTopic:
        targets = self._topic_target_repo.get_by_source(source_id)
        known = self._vocabulary.snapshot()
        library = {
            s.id: (s, document) for s in self._source_repo.list_all()
            if s.id is not None and (document := self._document_repo.get(s.id)) is not None
        }

        candidates: list[StoredCandidate] = []
        seen: set[str] = set()
        for target in targets:
            generated = self._generated_candidate(source_id, target)
            if generated is None:
                continue
            if generated.lemma in seen or known.is_known(generated.lemma):
                continue
            seen.add(generated.lemma)
            phrase = self._real_phrase(generated, target, library, known)
            candidates.append(
                generated if phrase is None else self._candidate_factory.build(
                    source_id=source_id,
                    surface_form=phrase.target,
                    context_fragment=phrase.text,
                    occurrences=SINGLE_OCCURRENCE,
                    origin=phrase.origin,
                ),
            )

        borrowed = sum(
            1 for c in candidates if c.origin and c.origin.kind == PhraseOriginKind.SOURCE
        )
        logger.info(
            "topic_phrase_collector: done (source_id=%d, targets=%d, candidates=%d, "
            "from_sources=%d)",
            source_id, len(targets), len(candidates), borrowed,
        )
        return CollectedTopic(
            candidates=candidates,
            text=PHRASE_SEPARATOR.join(c.context_fragment for c in candidates),
        )

    def _generated_candidate(self, source_id: int, target: TopicTarget) -> StoredCandidate | None:
        example = parse_marked_phrase(target.example)
        if example is None:
            logger.warning(
                "topic_phrase_collector: example without marked target (target_id=%s)",
                target.id,
            )
            return None
        return self._candidate_factory.build(
            source_id=source_id,
            surface_form=example.target,
            context_fragment=example.text,
            occurrences=SINGLE_OCCURRENCE,
            origin=PhraseOrigin.generated(),
        )

    def _real_phrase(
        self,
        generated: StoredCandidate,
        target: TopicTarget,
        library: dict[int, tuple[Source, Document]],
        vocabulary: Vocabulary,
    ) -> _Phrase | None:
        same_lemma = [
            c for c in self._candidate_repo.get_by_lemma(generated.lemma)
            if c.source_id in library
        ]
        best = pick_best_candidate_phrase(same_lemma, vocabulary)
        if best is not None:
            return _Phrase(
                text=best.context_fragment,
                target=best.surface_form or best.lemma,
                origin=PhraseOrigin.from_source(_title(library[best.source_id][0])),
            )

        variants = {target.phrase, generated.surface_form or generated.lemma}
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
        return _Phrase(
            text=sentence.text,
            target=sentence.target,
            origin=PhraseOrigin.from_source(_title(source)),
        )


def _title(source: Source) -> str:
    return source.title or ""
