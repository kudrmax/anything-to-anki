from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.analysis_dtos import (
    AnalyzeTextRequest,
    AnalyzeTextResponse,
    WordCandidateDTO,
)
from backend.domain.entities.word_candidate import WordCandidate
from backend.domain.exceptions import TextTooShortError
from backend.domain.services.candidate_filter import CandidateFilter
from backend.domain.services.fragment_extractor import FragmentExtractor
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.ports.text_cleaner import TextCleaner

DIRTY_THRESHOLD: int = 2


class AnalyzeTextUseCase:
    """Orchestrates the full text analysis pipeline (layers 2-3)."""

    def __init__(
        self,
        text_cleaner: TextCleaner,
        text_analyzer: TextAnalyzer,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
    ) -> None:
        self._text_cleaner = text_cleaner
        self._text_analyzer = text_analyzer
        self._cefr_classifier = cefr_classifier
        self._frequency_provider = frequency_provider
        self._candidate_filter = CandidateFilter()
        self._fragment_extractor = FragmentExtractor()

    def execute(self, request: AnalyzeTextRequest) -> AnalyzeTextResponse:
        user_level = CEFRLevel.from_str(request.user_level)

        # Layer 2: clean text
        cleaned = self._text_cleaner.clean(request.raw_text)
        if not cleaned.strip():
            raise TextTooShortError()

        # Layer 3: analyze
        tokens = self._text_analyzer.analyze(cleaned)
        if not tokens:
            return AnalyzeTextResponse(
                cleaned_text=cleaned,
                candidates=[],
                total_tokens=0,
                unique_lemmas=0,
            )

        # Collect candidates: group by (lemma, pos)
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
                fragment = self._fragment_extractor.extract(tokens, token.index)
                fragment_indices = self._fragment_extractor.extract_indices(
                    tokens, token.index
                )
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
                )
            candidate_map[key].occurrences += 1

        # Build sorted list
        candidates = self._build_sorted_candidates(candidate_map)

        unique_lemmas = len({t.lemma.lower() for t in tokens if t.is_alpha})

        return AnalyzeTextResponse(
            cleaned_text=cleaned,
            candidates=[self._to_dto(c) for c in candidates],
            total_tokens=len(tokens),
            unique_lemmas=unique_lemmas,
        )

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

    def _build_sorted_candidates(
        self, candidate_map: dict[tuple[str, str], _CandidateAccumulator]
    ) -> list[WordCandidate]:
        """Build and sort candidates: sweet_spot first, then by zipf asc, occurrences desc."""
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
                )
            )

        candidates.sort(
            key=lambda c: (
                not c.frequency_band.is_sweet_spot,  # sweet spot first
                c.frequency_band.zipf_value,  # rarer words first (lower zipf)
                -c.occurrences,  # more occurrences first
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
            cefr_level=candidate.cefr_level.name,
            zipf_frequency=candidate.frequency_band.zipf_value,
            is_sweet_spot=candidate.frequency_band.is_sweet_spot,
            context_fragment=candidate.context_fragment,
            fragment_purity=purity,
            occurrences=candidate.occurrences,
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
    )

    def __init__(
        self,
        cefr: CEFRLevel,
        freq_zipf: float,
        freq_sweet_spot: bool,
        fragment: str,
        unknown_count: int,
        pos_tag: str,
    ) -> None:
        self.cefr = cefr
        self.freq_zipf = freq_zipf
        self.freq_sweet_spot = freq_sweet_spot
        self.fragment = fragment
        self.unknown_count = unknown_count
        self.pos_tag = pos_tag
        self.occurrences = 0
