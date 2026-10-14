from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.dto.analysis_dtos import (
    AnalyzeTextRequest,
    AnalyzeTextResponse,
    WordCandidateDTO,
)
from backend.application.dto.document_dtos import DocumentPositionDTO
from backend.application.utils.word_knowledge import WordKnowledge
from backend.domain.entities.word_candidate import WordCandidate
from backend.domain.services.candidate_filter import CandidateFilter
from backend.domain.services.fragment_selection import (
    FragmentSelectionConfig,
    FragmentSelector,
)
from backend.domain.services.phrase_building import build_phrase
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.frequency_band import FrequencyBand

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.document_analyzer import DocumentAnalyzer
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.usage_source import UsageSource
    from backend.domain.services.document_layout import DocumentLayout
    from backend.domain.services.fragment_selection import SelectedFragment
    from backend.domain.services.fragment_selection.scoring.scorer import (
        UnknownCounter,
    )
    from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
    from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
    from backend.domain.value_objects.document import Document
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase

PHRASAL_VERB_POS = "VERB"
# Each occurrence costs a fragment selection; a few are enough to find a good phrase.
MAX_OCCURRENCES_COMPARED: int = 10


@dataclass(frozen=True)
class _Occurrence:
    """One place in the text where a target occurs."""

    target_index: int
    protected_indices: frozenset[int]
    pos: str
    tag: str
    surface_form: str
    cefr_breakdown: CEFRBreakdown | None


class AnalyzeTextUseCase:
    """Finds the words worth learning in a document, each with its phrase.

    One candidate per word: its phrase is the best one among the places
    where the word occurs. Words the user already knows are not candidates.
    The phrase and the target are kept as positions in the document.
    """

    def __init__(
        self,
        document_analyzer: DocumentAnalyzer,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        phrasal_verb_detector: PhrasalVerbDetector,
        fragment_selection_config: FragmentSelectionConfig | None = None,
        usage_lookup: UsageSource | None = None,
    ) -> None:
        self._document_analyzer = document_analyzer
        self._cefr_classifier = cefr_classifier
        self._frequency_provider = frequency_provider
        self._phrasal_verb_detector = phrasal_verb_detector
        self._candidate_filter = CandidateFilter()
        self._fragment_config = (
            fragment_selection_config or FragmentSelectionConfig()
        )
        self._selector = FragmentSelector(config=self._fragment_config)
        self._usage_lookup = usage_lookup

    def execute(self, document: Document, request: AnalyzeTextRequest) -> AnalyzeTextResponse:
        user_level = CEFRLevel.from_str(request.user_level)
        analyzed = self._document_analyzer.analyze(document)
        tokens, layout = analyzed.tokens, analyzed.layout
        logger.info(
            "analyze_text: start (text_len=%d, user_level=%s, known_words=%d, "
            "frequent_word_zipf=%s)",
            len(layout.text), user_level.name, len(request.vocabulary.known),
            request.frequent_word_zipf,
        )
        if not tokens:
            return AnalyzeTextResponse(
                text=layout.text, candidates=[], total_tokens=0, unique_lemmas=0,
            )

        knowledge = WordKnowledge(
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            user_level=user_level,
            vocabulary=request.vocabulary,
            frequent_zipf=request.frequent_word_zipf,
        )
        words = self._collect_words(tokens, knowledge, user_level)
        phrasal_verbs = self._collect_phrasal_verbs(tokens, knowledge)

        candidates = [
            self._build_candidate(
                lemma, occurrences, tokens, layout, knowledge, is_phrasal_verb=False,
            )
            for lemma, occurrences in words.items()
        ] + [
            self._build_candidate(
                lemma, occurrences, tokens, layout, knowledge, is_phrasal_verb=True,
            )
            for lemma, occurrences in phrasal_verbs.items()
        ]

        unique_lemmas = len({t.lemma.lower() for t in tokens if t.is_alpha})

        logger.info(
            "analyze_text: done (total_tokens=%d, unique_lemmas=%d, candidates=%d)",
            len(tokens), unique_lemmas, len(candidates),
        )
        return AnalyzeTextResponse(
            text=layout.text,
            candidates=[self._to_dto(c) for c in candidates],
            total_tokens=len(tokens),
            unique_lemmas=unique_lemmas,
        )

    def _collect_words(
        self,
        tokens: list[TokenData],
        knowledge: WordKnowledge,
        user_level: CEFRLevel,
    ) -> dict[str, list[_Occurrence]]:
        words: dict[str, list[_Occurrence]] = {}
        for token in tokens:
            if not self._candidate_filter.is_relevant_token(token):
                continue
            lemma = knowledge.lemma_of(token)
            if knowledge.is_known(lemma):
                continue
            breakdown = self._cefr_classifier.classify_detailed(lemma, token.tag)
            if not self._candidate_filter.is_above_user_level(
                breakdown.final_level, user_level,
            ):
                continue
            words.setdefault(lemma, []).append(_Occurrence(
                target_index=token.index,
                protected_indices=frozenset({token.index}),
                pos=token.pos,
                tag=token.tag,
                surface_form=token.text,
                cefr_breakdown=breakdown,
            ))
        return words

    def _collect_phrasal_verbs(
        self,
        tokens: list[TokenData],
        knowledge: WordKnowledge,
    ) -> dict[str, list[_Occurrence]]:
        phrasal_verbs: dict[str, list[_Occurrence]] = {}
        for match in self._phrasal_verb_detector.detect(tokens):
            if knowledge.is_known(match.lemma):
                continue
            verb_token = tokens[match.verb_index]
            phrasal_verbs.setdefault(match.lemma, []).append(_Occurrence(
                target_index=match.verb_index,
                protected_indices=frozenset({match.verb_index, *match.component_indices}),
                pos=PHRASAL_VERB_POS,
                tag=verb_token.tag,
                surface_form=match.surface_form,
                cefr_breakdown=None,
            ))
        return phrasal_verbs

    def _build_candidate(
        self,
        lemma: str,
        occurrences: list[_Occurrence],
        tokens: list[TokenData],
        layout: DocumentLayout,
        knowledge: WordKnowledge,
        *,
        is_phrasal_verb: bool,
    ) -> WordCandidate:
        fragment, occurrence = self._best_fragment(occurrences, tokens, knowledge)
        phrase_position = _position(layout, tokens, fragment.indices)
        phrase = _phrase(layout, phrase_position, tokens, fragment.indices, occurrence, knowledge)
        zipf = knowledge.zipf(lemma)
        breakdown = occurrence.cefr_breakdown
        return WordCandidate(
            lemma=lemma,
            pos=occurrence.pos,
            cefr_level=breakdown.final_level if breakdown else None,
            frequency_band=FrequencyBand.from_zipf(zipf),
            zipf_frequency=zipf,
            phrase=phrase,
            occurrences=len(occurrences),
            is_phrasal_verb=is_phrasal_verb,
            cefr_breakdown=breakdown,
            usage_distribution=(
                self._usage_lookup.get_distribution(lemma, occurrence.tag)
                if self._usage_lookup is not None
                else None
            ),
            phrase_position=phrase_position,
        )

    def _best_fragment(
        self,
        occurrences: list[_Occurrence],
        tokens: list[TokenData],
        knowledge: WordKnowledge,
    ) -> tuple[SelectedFragment, _Occurrence]:
        """The best phrase among the first occurrences; ties go to the earliest."""
        best: tuple[SelectedFragment, _Occurrence] | None = None
        for occurrence in occurrences[:MAX_OCCURRENCES_COMPARED]:
            selected = self._selector.select_scored(
                tokens=tokens,
                target_index=occurrence.target_index,
                protected_indices=occurrence.protected_indices,
                unknown_counter=self._unknown_counter(knowledge, occurrence.protected_indices),
            )
            if best is None or selected.score < best[0].score:
                best = (selected, occurrence)
        assert best is not None
        return best

    @staticmethod
    def _unknown_counter(
        knowledge: WordKnowledge, target_indices: frozenset[int],
    ) -> UnknownCounter:
        def count(indices: Sequence[int], tokens: list[TokenData]) -> int:
            return knowledge.count_unknowns(indices, tokens, target_indices)

        return count

    def _to_dto(self, candidate: WordCandidate) -> WordCandidateDTO:
        from backend.application.dto.cefr_dtos import breakdown_to_dto

        bd_dto = breakdown_to_dto(candidate.cefr_breakdown) if candidate.cefr_breakdown else None
        return WordCandidateDTO(
            lemma=candidate.lemma,
            pos=candidate.pos,
            cefr_level=candidate.cefr_level.name if candidate.cefr_level else None,
            zipf_frequency=candidate.zipf_frequency,
            is_sweet_spot=candidate.frequency_band.is_sweet_spot,
            phrase=candidate.phrase,
            occurrences=candidate.occurrences,
            is_phrasal_verb=candidate.is_phrasal_verb,
            cefr_breakdown=bd_dto,
            usage_distribution=(
                candidate.usage_distribution.to_dict()
                if candidate.usage_distribution
                else None
            ),
            phrase_position=(
                DocumentPositionDTO.from_position(candidate.phrase_position)
                if candidate.phrase_position
                else None
            ),
        )


def _position(
    layout: DocumentLayout, tokens: list[TokenData], indices: Iterable[int],
) -> DocumentPosition:
    """From the first word to the last: a phrase, or a target split by other words.

    Line breaks the parser keeps as tokens, and tokens without text, are not part of it.
    """
    chosen = [tokens[i] for i in indices if tokens[i].text.strip()]
    return layout.position(
        min(token.char_start for token in chosen), max(token.char_end for token in chosen),
    )


def _phrase(
    layout: DocumentLayout,
    position: DocumentPosition,
    tokens: list[TokenData],
    indices: Iterable[int],
    occurrence: _Occurrence,
    knowledge: WordKnowledge,
) -> Phrase:
    """The card phrase from the document already parsed: its words are the fragment's tokens,
    its target the occurrence's tokens."""
    start, _ = layout.span(position)
    facts = [knowledge.facts.facts(tokens[i], start) for i in indices]
    target = [
        (tokens[i].char_start - start, tokens[i].char_end - start)
        for i in sorted(occurrence.protected_indices)
    ]
    return build_phrase(layout.fragment(position), facts, target)
