from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.analysis_dtos import (
    AnalyzeTextRequest,
    AnalyzeTextResponse,
    WordCandidateDTO,
)
from backend.domain.entities.word_candidate import WordCandidate
from backend.domain.exceptions import TextTooShortError
from backend.domain.services.boundary_cleaner import (
    MIN_FRAGMENT_CONTENT_WORDS,
    BoundaryCleaner,
)
from backend.domain.services.candidate_filter import CandidateFilter
from backend.domain.services.clause_finder import ClauseFinder
from backend.domain.services.fragment_extractor import FragmentExtractor
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.ports.text_cleaner import TextCleaner
    from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector

DIRTY_THRESHOLD: int = 2

# Hard cap on fragment length: pieces longer than this get a heavy penalty
# in candidate ranking. Below this, length is not a ranking factor — only
# unknown_count and edge cleanliness matter.
LENGTH_HARD_CAP_CONTENT_WORDS: int = 25


class AnalyzeTextUseCase:
    """Orchestrates the full text analysis pipeline (layers 2-3)."""

    def __init__(
        self,
        text_cleaner: TextCleaner,
        text_analyzer: TextAnalyzer,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        phrasal_verb_detector: PhrasalVerbDetector,
    ) -> None:
        self._text_cleaner = text_cleaner
        self._text_analyzer = text_analyzer
        self._cefr_classifier = cefr_classifier
        self._frequency_provider = frequency_provider
        self._phrasal_verb_detector = phrasal_verb_detector
        self._candidate_filter = CandidateFilter()
        self._fragment_extractor = FragmentExtractor()
        self._boundary_cleaner = BoundaryCleaner()
        self._clause_finder = ClauseFinder()

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
                fragment_indices = self._select_best_fragment(
                    tokens=tokens,
                    target_index=token.index,
                    protected_indices=frozenset({token.index}),
                    user_level=user_level,
                )
                fragment = self._fragment_extractor.render(tokens, fragment_indices)
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
                fragment_indices = self._select_best_fragment(
                    tokens=tokens,
                    target_index=match.verb_index,
                    protected_indices=frozenset(
                        {match.verb_index, match.particle_index}
                    ),
                    user_level=user_level,
                )
                fragment = self._fragment_extractor.render(tokens, fragment_indices)
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

    def _select_best_fragment(
        self,
        tokens: list[TokenData],
        target_index: int,
        protected_indices: frozenset[int],
        user_level: CEFRLevel,
    ) -> list[int]:
        """Generate candidate fragments, clean each, pick best by score.

        Candidates considered (each cleaned via BoundaryCleaner before scoring):
        1. Subtree of every verb in the target's sentence (Level 2 pieces)
        2. Subtree of the target itself, then its head, head's head, ... up
           to ROOT (covers cases where target is a noun deep in another verb's
           clause, e.g. relcl)
        3. The full sentence
        4. The legacy FragmentExtractor output (for parity with Wave 1)

        Selection key (lower is better):
            (unknown_count, max(0, content_count - HARD_CAP), content_count)

        unknown_count is the central product metric ('target = single unknown').
        Length only matters as a hard cap above 25 content words; below that,
        edge cleanliness — already enforced by BoundaryCleaner — is what wins.
        """
        target_token = tokens[target_index]
        sent_idx = target_token.sent_index

        raw_candidates: list[list[int]] = []

        # 1. Verb-rooted pieces from the clause finder, restricted to ones
        #    that contain the target.
        for piece in self._clause_finder.find_pieces(tokens):
            if target_index in piece:
                raw_candidates.append(piece)

        # 2. Target's own subtree, then its ancestor chain.
        seen_roots: set[int] = set()
        cursor = target_index
        while cursor not in seen_roots:
            seen_roots.add(cursor)
            subtree = sorted(
                self._collect_subtree_in_sentence(tokens, cursor, sent_idx)
            )
            if subtree and target_index in subtree:
                raw_candidates.append(subtree)
            head = tokens[cursor].head_index
            if head == cursor:
                break
            cursor = head

        # 3. Full sentence.
        sentence = sorted(
            t.index for t in tokens if t.sent_index == sent_idx
        )
        if target_index in sentence:
            raw_candidates.append(sentence)

        # 4. Legacy FragmentExtractor output.
        legacy = self._fragment_extractor.extract_indices(tokens, target_index)
        if legacy and target_index in legacy:
            raw_candidates.append(legacy)

        # Clean each, drop ones that lost the target or are too short to be
        # informative (a target plus a couple of function words is degenerate).
        cleaned_candidates: list[list[int]] = []
        for cand in raw_candidates:
            cleaned = self._boundary_cleaner.clean(
                tokens, cand, protected_indices=protected_indices
            )
            if not cleaned or target_index not in cleaned:
                continue
            content_count = sum(
                1
                for idx in cleaned
                if tokens[idx].is_alpha and not tokens[idx].is_punct
            )
            if content_count < MIN_FRAGMENT_CONTENT_WORDS:
                continue
            cleaned_candidates.append(cleaned)

        if not cleaned_candidates:
            # Last-resort fallback: cleaned legacy, which is the Wave 1 behavior.
            return self._boundary_cleaner.clean(
                tokens, legacy, protected_indices=protected_indices
            )

        def score(indices: list[int]) -> tuple[int, int, int]:
            unknown = self._count_unknowns_in_fragment(indices, tokens, user_level)
            content_count = sum(
                1
                for idx in indices
                if tokens[idx].is_alpha and not tokens[idx].is_punct
            )
            length_penalty = max(0, content_count - LENGTH_HARD_CAP_CONTENT_WORDS)
            return (unknown, length_penalty, content_count)

        return min(cleaned_candidates, key=score)

    @staticmethod
    def _collect_subtree_in_sentence(
        tokens: list[TokenData], root_index: int, sent_idx: int
    ) -> set[int]:
        result: set[int] = set()
        stack = [root_index]
        while stack:
            idx = stack.pop()
            if idx in result:
                continue
            if tokens[idx].sent_index != sent_idx:
                continue
            result.add(idx)
            stack.extend(tokens[idx].children_indices)
        return result

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
