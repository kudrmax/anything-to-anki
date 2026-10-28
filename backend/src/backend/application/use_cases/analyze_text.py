from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.dto.analysis_dtos import (
    AnalyzeTextRequest,
    AnalyzeTextResponse,
    OccurrenceDTO,
    OccurrenceKeyDTO,
    WordDTO,
)
from backend.application.dto.document_dtos import DocumentPositionDTO
from backend.application.utils.word_knowledge import WordKnowledge
from backend.domain.services.candidate_filter import CandidateFilter
from backend.domain.services.fragment_selection import (
    FragmentSelectionConfig,
    FragmentSelector,
)
from backend.domain.services.long_operation_progress import no_report, part_of, scaled
from backend.domain.services.phrase_building import build_phrase
from backend.domain.value_objects.cefr_level import CEFRLevel

logger = logging.getLogger(__name__)

# Shares of the analysis, measured on a whole book: the parse 240 of 320 seconds, collecting
# the words and phrasal verbs over every token 15, each word's phrases the rest.
PARSE_SHARE = 0.75
COLLECT_SHARE = 0.05
# What collecting is reported after: the occurrences laid out, the words, the phrasal verbs.
COLLECT_STEPS = 3

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.document_analyzer import DocumentAnalyzer
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.usage_source import UsageSource
    from backend.domain.services.document_layout import DocumentLayout
    from backend.domain.services.fragment_selection.scoring.scorer import (
        UnknownCounter,
    )
    from backend.domain.services.long_operation_progress import PartReport
    from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
    from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
    from backend.domain.value_objects.document import Document
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase

PHRASAL_VERB_POS = "VERB"


@dataclass(frozen=True)
class _Occurrence:
    """One place in the text where a target occurs."""

    target_index: int
    protected_indices: frozenset[int]
    pos: str
    tag: str


@dataclass(frozen=True)
class _Form:
    """The part of speech of a word: its most frequent tag in the text."""

    pos: str
    tag: str


class AnalyzeTextUseCase:
    """Finds the words worth learning in a document, each with every place it occurs.

    A word is a lemma, or a phrasal verb; every occurrence comes with its phrase and the
    phrase's score. Words the user already knows, or below the user's level, are left out.
    Phrases and targets are kept as positions in the document.
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

    def execute(
        self, document: Document, request: AnalyzeTextRequest, report: PartReport = no_report,
    ) -> AnalyzeTextResponse:
        """`report` is told the share of the analysis done: the parse, the collecting of the
        words, then the occurrences of each word."""
        user_level = CEFRLevel.from_str(request.user_level)
        analyzed = self._document_analyzer.analyze(document, scaled(report, 0.0, PARSE_SHARE))
        tokens, layout = analyzed.tokens, analyzed.layout
        logger.info(
            "analyze_text: start (text_len=%d, user_level=%s, known_words=%d, "
            "frequent_word_zipf=%s)",
            len(layout.text), user_level.name, len(request.vocabulary.known),
            request.frequent_word_zipf,
        )
        if not tokens:
            report(1.0)
            return AnalyzeTextResponse(
                text=layout.text, words=[], total_tokens=0, unique_lemmas=0,
            )

        knowledge = WordKnowledge(
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            user_level=user_level,
            vocabulary=request.vocabulary,
            frequent_zipf=request.frequent_word_zipf,
        )
        collect_report = scaled(report, PARSE_SHARE, COLLECT_SHARE)
        occurrences = _Occurrences(tokens, layout, knowledge, self._selector)
        collect_report(part_of(1, COLLECT_STEPS))
        lemmas = self._collect_words(tokens, knowledge)
        collect_report(part_of(2, COLLECT_STEPS))
        phrasal_verbs = self._collect_phrasal_verbs(tokens, knowledge)
        collect_report(part_of(3, COLLECT_STEPS))
        words_from = PARSE_SHARE + COLLECT_SHARE
        words_report = scaled(report, words_from, 1.0 - words_from)
        # A word takes a while of its own and a while per occurrence: the share done is the
        # mean of the share of the words and that of their occurrences.
        found_by_word = [*lemmas.values(), *phrasal_verbs.values()]
        all_words, all_found = len(found_by_word), sum(map(len, found_by_word))
        words_done = found_done = 0

        def word_done(found: list[_Occurrence]) -> None:
            nonlocal words_done, found_done
            words_done += 1
            found_done += len(found)
            words_report((part_of(words_done, all_words) + part_of(found_done, all_found)) / 2)

        words: list[WordDTO] = []
        for lemma, found in lemmas.items():
            if (word := self._word(lemma, found, occurrences, user_level)) is not None:
                words.append(word)
            word_done(found)
        for lemma, found in phrasal_verbs.items():
            words.append(self._phrasal_verb(lemma, found, occurrences))
            word_done(found)
        report(1.0)

        unique_lemmas = len({t.lemma.lower() for t in tokens if t.is_alpha})
        logger.info(
            "analyze_text: done (total_tokens=%d, unique_lemmas=%d, words=%d, "
            "occurrences=%d)",
            len(tokens), unique_lemmas, len(words), sum(len(w.occurrences) for w in words),
        )
        return AnalyzeTextResponse(
            text=layout.text,
            words=words,
            total_tokens=len(tokens),
            unique_lemmas=unique_lemmas,
        )

    def _collect_words(
        self, tokens: list[TokenData], knowledge: WordKnowledge,
    ) -> dict[str, list[_Occurrence]]:
        words: dict[str, list[_Occurrence]] = {}
        for token in tokens:
            if not self._candidate_filter.is_relevant_token(token):
                continue
            lemma = knowledge.lemma_of(token)
            if knowledge.is_known_or_learning(lemma):
                continue
            words.setdefault(lemma, []).append(_Occurrence(
                target_index=token.index,
                protected_indices=frozenset({token.index}),
                pos=token.pos,
                tag=token.tag,
            ))
        return words

    def _collect_phrasal_verbs(
        self, tokens: list[TokenData], knowledge: WordKnowledge,
    ) -> dict[str, list[_Occurrence]]:
        phrasal_verbs: dict[str, list[_Occurrence]] = {}
        for match in self._phrasal_verb_detector.detect(tokens):
            if knowledge.is_known_or_learning(match.lemma):
                continue
            phrasal_verbs.setdefault(match.lemma, []).append(_Occurrence(
                target_index=match.verb_index,
                protected_indices=frozenset({match.verb_index, *match.component_indices}),
                pos=PHRASAL_VERB_POS,
                tag=tokens[match.verb_index].tag,
            ))
        return phrasal_verbs

    def _word(
        self,
        lemma: str,
        found: list[_Occurrence],
        occurrences: _Occurrences,
        user_level: CEFRLevel,
    ) -> WordDTO | None:
        """The word, unless its level is below the user's."""
        form = _most_frequent_form(found)
        breakdown = self._cefr_classifier.classify_detailed(lemma, form.tag)
        if not self._candidate_filter.is_learned_at_user_level(breakdown.final_level, user_level):
            return None
        return self._dto(
            lemma, form, found, occurrences, breakdown=breakdown, is_phrasal_verb=False,
        )

    def _phrasal_verb(
        self, lemma: str, found: list[_Occurrence], occurrences: _Occurrences,
    ) -> WordDTO:
        form = _most_frequent_form(found)
        return self._dto(lemma, form, found, occurrences, breakdown=None, is_phrasal_verb=True)

    def _dto(
        self,
        lemma: str,
        form: _Form,
        found: list[_Occurrence],
        occurrences: _Occurrences,
        *,
        breakdown: CEFRBreakdown | None,
        is_phrasal_verb: bool,
    ) -> WordDTO:
        from backend.application.dto.cefr_dtos import breakdown_to_dto

        usage = (
            self._usage_lookup.get_distribution(lemma, form.tag)
            if self._usage_lookup is not None
            else None
        )
        return WordDTO(
            lemma=lemma,
            is_phrasal_verb=is_phrasal_verb,
            pos=form.pos,
            cefr_level=breakdown.final_level.name if breakdown else None,
            cefr_breakdown=breakdown_to_dto(breakdown) if breakdown else None,
            zipf_frequency=occurrences.knowledge.zipf(lemma),
            usage_distribution=usage.to_dict() if usage else None,
            occurrences=[occurrences.dto(occurrence) for occurrence in found],
        )


class _Occurrences:
    """Turns the occurrences of one parsed document into their phrases."""

    def __init__(
        self,
        tokens: list[TokenData],
        layout: DocumentLayout,
        knowledge: WordKnowledge,
        selector: FragmentSelector,
    ) -> None:
        self._tokens = tokens
        self._layout = layout
        self.knowledge = knowledge
        self._selector = selector

    def dto(self, occurrence: _Occurrence) -> OccurrenceDTO:
        selected = self._selector.select_scored(
            tokens=self._tokens,
            target_index=occurrence.target_index,
            protected_indices=occurrence.protected_indices,
            unknown_counter=self._unknown_counter(occurrence.protected_indices),
        )
        position = _position(self._layout, self._tokens, selected.indices)
        phrase = _phrase(
            self._layout, position, self._tokens, selected.indices, occurrence, self.knowledge,
        )
        return OccurrenceDTO(
            phrase=phrase,
            phrase_position=DocumentPositionDTO.from_position(position),
            # The one rule of a key, as for a phrase added by hand: where the phrase's target
            # starts — a phrase word may hold several tokens ("self-esteem").
            key=OccurrenceKeyDTO.from_key(self._layout.target_key(position, phrase)),
            fragment_score=selected.score.as_number(),
        )

    def _unknown_counter(self, target_indices: frozenset[int]) -> UnknownCounter:
        knowledge = self.knowledge

        def count(indices: Sequence[int], tokens: list[TokenData]) -> int:
            return knowledge.count_unknowns(indices, tokens, target_indices)

        return count


def _most_frequent_form(found: list[_Occurrence]) -> _Form:
    """The most frequent tag, and its most frequent part of speech; ties go to the first
    in alphabetical order, so the order of the occurrences does not matter."""
    tags = Counter(occurrence.tag for occurrence in found)
    tag = min(tags, key=lambda t: (-tags[t], t))
    parts = Counter(occurrence.pos for occurrence in found if occurrence.tag == tag)
    return _Form(pos=min(parts, key=lambda p: (-parts[p], p)), tag=tag)


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
