from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
    from backend.domain.value_objects.phrase_origin import PhraseOrigin

FALLBACK_POS = "X"
FALLBACK_TAG = "NN"
PHRASAL_VERB_POS = "VERB"
PHRASAL_VERB_TAG = "VB"
COLLOCATION_POS = "X"
COLLOCATION_TAG = "NN"
CLEAN_PURITY = "clean"


@dataclass(frozen=True)
class _Lexeme:
    lemma: str
    pos: str
    tag: str
    is_phrasal_verb: bool


class CandidateFactory:
    """Builds a candidate for a target the user (or a topic) picked explicitly.

    Runs the same enrichment as automatic processing — lemma, POS, CEFR,
    frequency — but bypasses the CEFR level gate: the target is always kept.
    """

    def __init__(
        self,
        text_analyzer: TextAnalyzer,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        phrasal_verb_detector: PhrasalVerbDetector,
    ) -> None:
        self._text_analyzer = text_analyzer
        self._cefr_classifier = cefr_classifier
        self._frequency_provider = frequency_provider
        self._phrasal_verb_detector = phrasal_verb_detector

    def build(
        self,
        source_id: int,
        surface_form: str,
        context_fragment: str,
        occurrences: int,
        origin: PhraseOrigin | None = None,
    ) -> StoredCandidate:
        lexeme = self._resolve_lexeme(surface_form, context_fragment)
        breakdown = self._cefr_classifier.classify_detailed(lexeme.lemma, lexeme.tag)
        cefr = breakdown.final_level
        return StoredCandidate(
            source_id=source_id,
            lemma=lexeme.lemma,
            pos=lexeme.pos,
            cefr_level=cefr.name if cefr != CEFRLevel.UNKNOWN else None,
            zipf_frequency=self._frequency_provider.get_zipf_value(lexeme.lemma),
            context_fragment=context_fragment,
            fragment_purity=CLEAN_PURITY,
            occurrences=occurrences,
            surface_form=surface_form,
            is_phrasal_verb=lexeme.is_phrasal_verb,
            status=CandidateStatus.PENDING,
            cefr_breakdown=breakdown,
            origin=origin,
        )

    def _resolve_lexeme(self, surface_form: str, context_fragment: str) -> _Lexeme:
        tokens = self._text_analyzer.analyze(context_fragment)
        surface_lower = surface_form.lower()

        pv_match = next(
            (
                m for m in self._phrasal_verb_detector.detect(tokens)
                if m.surface_form.lower() == surface_lower
            ),
            None,
        )
        if pv_match:
            verb_token = next((t for t in tokens if t.index == pv_match.verb_index), None)
            return _Lexeme(
                lemma=pv_match.lemma,
                pos=PHRASAL_VERB_POS,
                tag=verb_token.tag if verb_token else PHRASAL_VERB_TAG,
                is_phrasal_verb=True,
            )

        matching_token = _first_word(t for t in tokens if t.text.lower() == surface_lower)
        if matching_token is None:
            # Surface form is not a single token of the context: analyse it alone.
            surface_tokens = self._text_analyzer.analyze(surface_form)
            if len(surface_tokens) > 1:
                return _collocation(surface_tokens)
            matching_token = _first_word(surface_tokens)
        if matching_token is None:
            return _Lexeme(
                lemma=surface_lower, pos=FALLBACK_POS, tag=FALLBACK_TAG, is_phrasal_verb=False,
            )
        return _Lexeme(
            lemma=matching_token.lemma.lower(),
            pos=matching_token.pos,
            tag=matching_token.tag,
            is_phrasal_verb=False,
        )


def _collocation(tokens: list[TokenData]) -> _Lexeme:
    """Several words learned together ("make a decision", "counter-offer")."""
    lemma = "".join(t.lemma.lower() + t.whitespace_after for t in tokens).strip()
    return _Lexeme(lemma=lemma, pos=COLLOCATION_POS, tag=COLLOCATION_TAG, is_phrasal_verb=False)


def _first_word(tokens: Iterable[TokenData]) -> TokenData | None:
    return next((t for t in tokens if t.is_alpha and not t.is_punct), None)
