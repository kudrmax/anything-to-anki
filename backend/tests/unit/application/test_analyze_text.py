from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.dto.analysis_dtos import AnalyzeTextRequest
from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
from backend.domain.entities.token_data import TokenData
from backend.domain.exceptions import TextTooShortError
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.frequency_band import FrequencyBand


def _make_token(
    index: int,
    text: str,
    lemma: str,
    pos: str = "NOUN",
    tag: str = "NN",
    *,
    head_index: int | None = None,
    children: tuple[int, ...] = (),
    is_stop: bool = False,
    is_propn: bool = False,
    sent_index: int = 0,
) -> TokenData:
    return TokenData(
        index=index,
        text=text,
        lemma=lemma,
        pos=pos,
        tag=tag,
        head_index=head_index if head_index is not None else index,
        children_indices=children,
        is_punct=False,
        is_stop=is_stop,
        is_alpha=True,
        is_propn=is_propn,
        sent_index=sent_index,
    )


def _create_use_case(
    cleaned_text: str = "test text",
    tokens: list[TokenData] | None = None,
    cefr_map: dict[str, CEFRLevel] | None = None,
    freq_map: dict[str, float] | None = None,
) -> AnalyzeTextUseCase:
    text_cleaner = MagicMock()
    text_cleaner.clean.return_value = cleaned_text

    text_analyzer = MagicMock()
    text_analyzer.analyze.return_value = tokens or []

    cefr_classifier = MagicMock()
    _cefr = cefr_map or {}
    cefr_classifier.classify.side_effect = lambda lemma, tag: _cefr.get(
        lemma, CEFRLevel.A1
    )
    cefr_classifier.classify_detailed.side_effect = lambda lemma, tag: CEFRBreakdown(
        final_level=_cefr.get(lemma, CEFRLevel.A1),
        decision_method="voting",
        priority_vote=None,
        votes=[],
    )

    frequency_provider = MagicMock()
    _freq = freq_map or {}
    frequency_provider.get_frequency.side_effect = lambda lemma: FrequencyBand.from_zipf(
        _freq.get(lemma, 5.0)
    )
    frequency_provider.get_zipf_value.side_effect = lambda lemma: _freq.get(lemma, 5.0)

    phrasal_verb_detector = MagicMock()
    phrasal_verb_detector.detect.return_value = []

    return AnalyzeTextUseCase(
        text_cleaner=text_cleaner,
        text_analyzer=text_analyzer,
        cefr_classifier=cefr_classifier,
        frequency_provider=frequency_provider,
        phrasal_verb_detector=phrasal_verb_detector,
    )


@pytest.mark.unit
class TestAnalyzeTextUseCase:
    def test_empty_text_raises(self) -> None:
        use_case = _create_use_case(cleaned_text="")
        request = AnalyzeTextRequest(raw_text="...", user_level="B1")
        with pytest.raises(TextTooShortError):
            use_case.execute(request)

    def test_no_tokens_returns_empty(self) -> None:
        use_case = _create_use_case(cleaned_text="hello", tokens=[])
        request = AnalyzeTextRequest(raw_text="hello", user_level="B1")
        response = use_case.execute(request)
        assert response.candidates == []
        assert response.total_tokens == 0

    def test_filters_below_user_level(self) -> None:
        tokens = [_make_token(0, "happy", "happy")]
        use_case = _create_use_case(
            cleaned_text="happy",
            tokens=tokens,
            cefr_map={"happy": CEFRLevel.A1},
        )
        request = AnalyzeTextRequest(raw_text="happy", user_level="B1")
        response = use_case.execute(request)
        assert len(response.candidates) == 0

    def test_includes_above_user_level(self) -> None:
        tokens = [_make_token(0, "relentless", "relentless")]
        use_case = _create_use_case(
            cleaned_text="relentless",
            tokens=tokens,
            cefr_map={"relentless": CEFRLevel.C1},
            freq_map={"relentless": 3.5},
        )
        request = AnalyzeTextRequest(raw_text="relentless", user_level="B1")
        response = use_case.execute(request)
        assert len(response.candidates) == 1
        assert response.candidates[0].lemma == "relentless"
        assert response.candidates[0].cefr_level == "C1"

    def test_deduplicates_same_lemma(self) -> None:
        tokens = [
            _make_token(0, "pursue", "pursue", tag="VB"),
            _make_token(1, "pursuing", "pursue", tag="VBG"),
        ]
        use_case = _create_use_case(
            cleaned_text="pursue pursuing",
            tokens=tokens,
            cefr_map={"pursue": CEFRLevel.B2},
            freq_map={"pursue": 4.0},
        )
        request = AnalyzeTextRequest(raw_text="pursue pursuing", user_level="B1")
        response = use_case.execute(request)
        # Both have same (lemma, pos) = ("pursue", "NOUN"), should deduplicate
        assert len(response.candidates) == 1
        assert response.candidates[0].occurrences == 2

    def test_both_candidates_returned(self) -> None:
        tokens = [
            _make_token(0, "ubiquitous", "ubiquitous"),
            _make_token(1, "pursuit", "pursuit"),
        ]
        use_case = _create_use_case(
            cleaned_text="ubiquitous pursuit",
            tokens=tokens,
            cefr_map={
                "ubiquitous": CEFRLevel.C2,
                "pursuit": CEFRLevel.B2,
            },
            freq_map={
                "ubiquitous": 2.5,
                "pursuit": 4.0,
            },
        )
        request = AnalyzeTextRequest(raw_text="ubiquitous pursuit", user_level="B1")
        response = use_case.execute(request)
        assert len(response.candidates) == 2
        lemmas = {c.lemma for c in response.candidates}
        assert lemmas == {"pursuit", "ubiquitous"}

    def test_filters_stop_words(self) -> None:
        tokens = [_make_token(0, "the", "the", is_stop=True)]
        use_case = _create_use_case(
            cleaned_text="the",
            tokens=tokens,
            cefr_map={"the": CEFRLevel.C1},
        )
        request = AnalyzeTextRequest(raw_text="the", user_level="B1")
        response = use_case.execute(request)
        assert len(response.candidates) == 0

    def test_fragment_purity(self) -> None:
        tokens = [_make_token(0, "relentless", "relentless")]
        use_case = _create_use_case(
            cleaned_text="relentless",
            tokens=tokens,
            cefr_map={"relentless": CEFRLevel.C1},
            freq_map={"relentless": 3.5},
        )
        request = AnalyzeTextRequest(raw_text="relentless", user_level="B1")
        response = use_case.execute(request)
        assert response.candidates[0].fragment_purity in ("clean", "dirty")
