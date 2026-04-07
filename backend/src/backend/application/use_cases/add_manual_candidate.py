from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import StoredCandidateDTO
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.text_analyzer import TextAnalyzer
    from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector


class AddManualCandidateUseCase:
    """Manually adds a word candidate selected by the user during review.

    Runs the same enrichment pipeline as automatic processing (lemma, POS, CEFR,
    frequency) but bypasses the CEFR level gate — the candidate is always saved.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        text_analyzer: TextAnalyzer,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        phrasal_verb_detector: PhrasalVerbDetector,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._text_analyzer = text_analyzer
        self._cefr_classifier = cefr_classifier
        self._frequency_provider = frequency_provider
        self._phrasal_verb_detector = phrasal_verb_detector

    def execute(
        self,
        source_id: int,
        surface_form: str,
        context_fragment: str,
    ) -> StoredCandidateDTO:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)

        tokens = self._text_analyzer.analyze(context_fragment)
        pv_matches = self._phrasal_verb_detector.detect(tokens)

        surface_lower = surface_form.lower()
        pv_match = next(
            (m for m in pv_matches if m.surface_form.lower() == surface_lower),
            None,
        )

        if pv_match:
            lemma = pv_match.lemma
            pos = "VERB"
            is_phrasal_verb = True
            token_map = {t.index: t for t in tokens}
            verb_token = token_map.get(pv_match.verb_index)
            tag = verb_token.tag if verb_token else "VB"
        else:
            matching_token = next(
                (
                    t for t in tokens
                    if t.text.lower() == surface_lower and t.is_alpha and not t.is_punct
                ),
                None,
            )
            if matching_token is None:
                # Fallback: analyse surface_form directly
                sf_tokens = self._text_analyzer.analyze(surface_form)
                matching_token = next(
                    (t for t in sf_tokens if t.is_alpha and not t.is_punct),
                    None,
                )
            lemma = matching_token.lemma.lower() if matching_token else surface_lower
            pos = matching_token.pos if matching_token else "X"
            tag = matching_token.tag if matching_token else "NN"
            is_phrasal_verb = False

        cefr = self._cefr_classifier.classify(lemma, tag)
        cefr_level_str: str | None = cefr.name if cefr != CEFRLevel.UNKNOWN else None

        freq = self._frequency_provider.get_frequency(lemma)

        source_text = source.cleaned_text or source.raw_text
        occurrences = max(source_text.lower().count(surface_lower), 1)

        candidate = StoredCandidate(
            source_id=source_id,
            lemma=lemma,
            pos=pos,
            cefr_level=cefr_level_str,
            zipf_frequency=freq.zipf_value,
            is_sweet_spot=freq.is_sweet_spot,
            context_fragment=context_fragment,
            fragment_purity="clean",
            occurrences=occurrences,
            surface_form=surface_form,
            is_phrasal_verb=is_phrasal_verb,
            status=CandidateStatus.PENDING,
        )
        saved = self._candidate_repo.create_batch([candidate])[0]

        return StoredCandidateDTO(
            id=saved.id,  # type: ignore[arg-type]
            lemma=saved.lemma,
            pos=saved.pos,
            cefr_level=saved.cefr_level,
            zipf_frequency=saved.zipf_frequency,
            is_sweet_spot=saved.is_sweet_spot,
            context_fragment=saved.context_fragment,
            fragment_purity=saved.fragment_purity,
            occurrences=saved.occurrences,
            status=saved.status.value,
            surface_form=saved.surface_form,
            is_phrasal_verb=saved.is_phrasal_verb,
        )
