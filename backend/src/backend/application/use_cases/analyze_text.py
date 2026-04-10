from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.analysis_dtos import (
    AnalyzeTextRequest,
    AnalyzeTextResponse,
    WordCandidateDTO,
)
from backend.domain.entities.word_candidate import WordCandidate
from backend.domain.exceptions import TextTooShortError
from backend.domain.services.candidate_filter import CandidateFilter
from backend.domain.services.fragment_selection import (
    FragmentSelectionConfig,
    FragmentSelector,
)
from backend.domain.services.fragment_selection.rendering import render_fragment
from backend.domain.value_objects.cefr_level import CEFRLevel

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.ports.text_cleaner import TextCleaner
    from backend.domain.services.fragment_selection.scoring.scorer import (
        UnknownCounter,
    )
    from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector

DIRTY_THRESHOLD: int = 2


class AnalyzeTextUseCase:
    """Orchestrates the full text analysis pipeline (layers 2-3)."""

    def __init__(
        self,
        text_cleaner: TextCleaner,
        text_analyzer: TextAnalyzer,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        phrasal_verb_detector: PhrasalVerbDetector,
        fragment_selection_config: FragmentSelectionConfig | None = None,
    ) -> None:
        self._text_cleaner = text_cleaner
        self._text_analyzer = text_analyzer
        self._cefr_classifier = cefr_classifier
        self._frequency_provider = frequency_provider
        self._phrasal_verb_detector = phrasal_verb_detector
        self._candidate_filter = CandidateFilter()
        self._fragment_config = (
            fragment_selection_config or FragmentSelectionConfig()
        )
        self._selector = FragmentSelector(config=self._fragment_config)

    def execute(self, request: AnalyzeTextRequest) -> AnalyzeTextResponse:
        user_level = CEFRLevel.from_str(request.user_level)
        logger.info(
            "analyze_text: start (raw_text_len=%d, user_level=%s)",
            len(request.raw_text or ""), user_level.name,
        )

        # Layer 2: clean text
        cleaned = self._text_cleaner.clean(request.raw_text)
        if not cleaned.strip():
            logger.warning(
                "analyze_text: cleaned text is empty (raw_text_len=%d)",
                len(request.raw_text or ""),
            )
            raise TextTooShortError()

        # Layer 3: analyze
        tokens = self._text_analyzer.analyze(cleaned)
        if not tokens:
            logger.info(
                "analyze_text: no tokens after analysis (cleaned_len=%d)",
                len(cleaned),
            )
            return AnalyzeTextResponse(
                cleaned_text=cleaned,
                candidates=[],
                total_tokens=0,
                unique_lemmas=0,
            )

        # Collect single-word candidates: group by (lemma, pos)
        candidate_map: dict[tuple[str, str], _CandidateAccumulator] = {}

        for token in tokens:
            if not self._candidate_filter.is_relevant_token(token):
                continue

            cefr = self._cefr_classifier.classify(token.lemma, token.tag)
            if not self._candidate_filter.is_above_user_level(cefr, user_level):
                continue

            key = (token.lemma.lower(), token.pos)
            if key not in candidate_map:
                freq = self._frequency_provider.get_frequency(token.lemma.lower())
                fragment_indices = self._selector.select(
                    tokens=tokens,
                    target_index=token.index,
                    protected_indices=frozenset({token.index}),
                    unknown_counter=self._make_unknown_counter(user_level),
                )
                fragment = render_fragment(tokens, fragment_indices)
                unknown_count = self._count_unknowns_in_fragment(
                    fragment_indices, tokens, user_level
                )
                candidate_map[key] = _CandidateAccumulator(
                    cefr=cefr,
                    freq_zipf=freq.zipf_value,
                    freq_sweet_spot=freq.is_sweet_spot,
                    fragment=fragment,
                    unknown_count=unknown_count,
                    pos_tag=token.tag,
                    is_phrasal_verb=False,
                )
            candidate_map[key].occurrences += 1

        # Collect phrasal verb candidates
        self._collect_phrasal_verbs(tokens, candidate_map, user_level)

        # Build sorted list
        candidates = self._build_sorted_candidates(candidate_map)

        unique_lemmas = len({t.lemma.lower() for t in tokens if t.is_alpha})

        logger.info(
            "analyze_text: done (total_tokens=%d, unique_lemmas=%d, candidates=%d)",
            len(tokens), unique_lemmas, len(candidates),
        )
        return AnalyzeTextResponse(
            cleaned_text=cleaned,
            candidates=[self._to_dto(c) for c in candidates],
            total_tokens=len(tokens),
            unique_lemmas=unique_lemmas,
        )

    def _collect_phrasal_verbs(
        self,
        tokens: list[TokenData],
        candidate_map: dict[tuple[str, str], _CandidateAccumulator],
        user_level: CEFRLevel,
    ) -> None:
        """Detect phrasal verbs and add them to candidate_map."""
        token_map = {t.index: t for t in tokens}
        matches = self._phrasal_verb_detector.detect(tokens)

        for match in matches:
            key = (match.lemma, "VERB")
            verb_token = token_map[match.verb_index]

            if key not in candidate_map:
                freq = self._frequency_provider.get_frequency(match.lemma)
                fragment_indices = self._selector.select(
                    tokens=tokens,
                    target_index=match.verb_index,
                    protected_indices=frozenset(
                        {match.verb_index, match.particle_index}
                    ),
                    unknown_counter=self._make_unknown_counter(user_level),
                )
                fragment = render_fragment(tokens, fragment_indices)
                unknown_count = self._count_unknowns_in_fragment(
                    fragment_indices, tokens, user_level
                )
                candidate_map[key] = _CandidateAccumulator(
                    cefr=None,
                    freq_zipf=freq.zipf_value,
                    freq_sweet_spot=freq.is_sweet_spot,
                    fragment=fragment,
                    unknown_count=unknown_count,
                    pos_tag=verb_token.tag,
                    is_phrasal_verb=True,
                    surface_form=match.surface_form,
                )
            candidate_map[key].occurrences += 1

    def _count_unknowns_in_fragment(
        self,
        fragment_indices: list[int],
        tokens: list[TokenData],
        user_level: CEFRLevel,
    ) -> int:
        """Count words in the fragment that are above user level (excluding target)."""
        count = 0
        for idx in fragment_indices:
            token = tokens[idx]
            if not self._candidate_filter.is_relevant_token(token):
                continue
            cefr = self._cefr_classifier.classify(token.lemma, token.tag)
            if self._candidate_filter.is_above_user_level(cefr, user_level):
                count += 1
        return count

    def _make_unknown_counter(self, user_level: CEFRLevel) -> UnknownCounter:
        """Build an UnknownCounter closure for FragmentSelector."""

        def count(
            indices: Sequence[int], tokens: list[TokenData]
        ) -> int:
            return self._count_unknowns_in_fragment(
                list(indices), tokens, user_level
            )

        return count

    def _build_sorted_candidates(
        self, candidate_map: dict[tuple[str, str], _CandidateAccumulator]
    ) -> list[WordCandidate]:
        """Build and sort candidates: phrasal verbs first, then sweet_spot, then zipf asc."""
        from backend.domain.value_objects.frequency_band import FrequencyBand

        candidates: list[WordCandidate] = []
        for (lemma, pos), acc in candidate_map.items():
            candidates.append(
                WordCandidate(
                    lemma=lemma,
                    pos=pos,
                    cefr_level=acc.cefr,
                    frequency_band=FrequencyBand.from_zipf(acc.freq_zipf),
                    context_fragment=acc.fragment,
                    fragment_unknown_count=acc.unknown_count,
                    occurrences=acc.occurrences,
                    is_phrasal_verb=acc.is_phrasal_verb,
                    surface_form=acc.surface_form,
                )
            )

        candidates.sort(
            key=lambda c: (
                not c.is_phrasal_verb,               # phrasal verbs first
                not c.frequency_band.is_sweet_spot,  # sweet spot first
                c.frequency_band.zipf_value,          # rarer words first (lower zipf)
                -c.occurrences,                       # more occurrences first
            )
        )
        return candidates

    def _to_dto(self, candidate: WordCandidate) -> WordCandidateDTO:
        purity = (
            "clean" if candidate.fragment_unknown_count < DIRTY_THRESHOLD else "dirty"
        )
        return WordCandidateDTO(
            lemma=candidate.lemma,
            pos=candidate.pos,
            cefr_level=candidate.cefr_level.name if candidate.cefr_level else None,
            zipf_frequency=candidate.frequency_band.zipf_value,
            is_sweet_spot=candidate.frequency_band.is_sweet_spot,
            context_fragment=candidate.context_fragment,
            fragment_purity=purity,
            occurrences=candidate.occurrences,
            is_phrasal_verb=candidate.is_phrasal_verb,
            surface_form=candidate.surface_form,
        )


class _CandidateAccumulator:
    """Mutable accumulator used during candidate collection."""

    __slots__ = (
        "cefr",
        "freq_zipf",
        "freq_sweet_spot",
        "fragment",
        "unknown_count",
        "pos_tag",
        "occurrences",
        "is_phrasal_verb",
        "surface_form",
    )

    def __init__(
        self,
        cefr: CEFRLevel | None,
        freq_zipf: float,
        freq_sweet_spot: bool,
        fragment: str,
        unknown_count: int,
        pos_tag: str,
        is_phrasal_verb: bool,
        surface_form: str | None = None,
    ) -> None:
        self.cefr = cefr
        self.freq_zipf = freq_zipf
        self.freq_sweet_spot = freq_sweet_spot
        self.fragment = fragment
        self.unknown_count = unknown_count
        self.pos_tag = pos_tag
        self.is_phrasal_verb = is_phrasal_verb
        self.surface_form = surface_form
        self.occurrences = 0
