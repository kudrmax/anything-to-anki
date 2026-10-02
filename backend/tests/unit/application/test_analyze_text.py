from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from backend.application.dto.analysis_dtos import AnalyzeTextRequest, WordCandidateDTO
from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
from backend.domain.entities.token_data import TokenData
from backend.domain.exceptions import TextTooShortError
from backend.domain.services.phrasal_verb_detector import PhrasalVerbMatch
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

    text_normalizer = MagicMock()
    text_normalizer.normalize.side_effect = lambda t: t  # passthrough

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
        priority_votes=[],
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
        text_normalizer=text_normalizer,
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


def _sentence(start: int, sent_index: int, lemmas: list[str]) -> list[TokenData]:
    return [
        replace(_make_token(start + i, lemma, lemma, sent_index=sent_index), whitespace_after=" ")
        for i, lemma in enumerate(lemmas)
    ]


def _run(
    tokens: list[TokenData],
    cefr_map: dict[str, CEFRLevel],
    freq_map: dict[str, float] | None = None,
    known: frozenset[str] = frozenset(),
    threshold: str = "4.5",
) -> list[WordCandidateDTO]:
    use_case = _create_use_case(
        cleaned_text=" ".join(t.text for t in tokens),
        tokens=tokens,
        cefr_map=cefr_map,
        freq_map=freq_map or {},
    )
    request = AnalyzeTextRequest(
        raw_text="text", user_level="B1", known_lemmas=known,
        frequent_word_threshold=threshold,
    )
    return use_case.execute(request).candidates


EASY = {"one": 3.0, "two": 3.0, "three": 3.0, "four": 3.0, "five": 3.0, "six": 3.0}


@pytest.mark.unit
class TestAnalyzeTextKnownWords:
    def test_known_word_is_not_a_candidate(self) -> None:
        tokens = [_make_token(0, "divorced", "divorce", pos="VERB", tag="VBN")]
        candidates = _run(tokens, {"divorce": CEFRLevel.B2}, known=frozenset({"divorce"}))
        assert candidates == []

    def test_known_phrasal_verb_is_not_a_candidate(self) -> None:
        tokens = [
            _make_token(0, "made", "make", pos="VERB", tag="VBD"),
            _make_token(1, "up", "up", pos="ADP", tag="RP"),
        ]
        use_case = _create_use_case(cleaned_text="made up", tokens=tokens)
        use_case._phrasal_verb_detector.detect.return_value = [  # type: ignore[attr-defined]
            PhrasalVerbMatch(
                verb_index=0, component_indices=(1,), lemma="make up", surface_form="made up",
            ),
        ]
        request = AnalyzeTextRequest(
            raw_text="made up", user_level="B1", known_lemmas=frozenset({"make up"}),
        )
        assert use_case.execute(request).candidates == []


@pytest.mark.unit
class TestAnalyzeTextOneCardPerWord:
    def test_same_word_as_different_parts_of_speech_is_one_candidate(self) -> None:
        tokens = [
            _make_token(0, "premium", "premium", pos="ADJ", tag="JJ"),
            _make_token(1, "premium", "premium", pos="NOUN", tag="NN"),
        ]
        candidates = _run(tokens, {"premium": CEFRLevel.B2}, {"premium": 4.3})
        assert len(candidates) == 1
        assert candidates[0].occurrences == 2

    def test_lemmatizer_non_word_falls_back_to_word_as_written(self) -> None:
        tokens = [_make_token(0, "syphilis", "syphili")]
        candidates = _run(
            tokens, {"syphilis": CEFRLevel.C2}, {"syphili": 0.0, "syphilis": 3.1},
        )
        assert [c.lemma for c in candidates] == ["syphilis"]


@pytest.mark.unit
class TestAnalyzeTextPhraseChoice:
    def test_phrase_where_target_is_the_only_unknown_word_wins(self) -> None:
        first = _sentence(0, 0, ["one", "rival", "two", "three", "feast"])
        second = _sentence(5, 1, ["four", "five", "six", "one", "feast"])
        candidates = _run(
            first + second,
            {"feast": CEFRLevel.C1, "rival": CEFRLevel.C1},
            {**EASY, "feast": 3.9, "rival": 3.9},
        )
        feast = next(c for c in candidates if c.lemma == "feast")
        assert feast.context_fragment == "four five six one feast"
        assert feast.fragment_unknown_count == 0
        assert feast.fragment_purity == "clean"

    def test_other_unknown_word_makes_phrase_dirty(self) -> None:
        tokens = _sentence(0, 0, ["one", "rival", "two", "three", "feast"])
        candidates = _run(
            tokens, {"feast": CEFRLevel.C1, "rival": CEFRLevel.C1},
            {**EASY, "feast": 3.9, "rival": 3.9},
        )
        feast = next(c for c in candidates if c.lemma == "feast")
        assert feast.fragment_unknown_count == 1
        assert feast.fragment_purity == "dirty"

    def test_known_neighbour_is_not_counted_as_unknown(self) -> None:
        tokens = _sentence(0, 0, ["one", "rival", "two", "three", "feast"])
        candidates = _run(
            tokens, {"feast": CEFRLevel.C1, "rival": CEFRLevel.C1},
            {**EASY, "feast": 3.9, "rival": 3.9}, known=frozenset({"rival"}),
        )
        assert candidates[0].lemma == "feast"
        assert candidates[0].fragment_unknown_count == 0

    def test_frequent_neighbour_is_not_counted_as_unknown(self) -> None:
        tokens = _sentence(0, 0, ["one", "concept", "two", "three", "feast"])
        candidates = _run(
            tokens, {"feast": CEFRLevel.C1, "concept": CEFRLevel.B2},
            {**EASY, "feast": 3.9, "concept": 4.77},
        )
        feast = next(c for c in candidates if c.lemma == "feast")
        assert feast.fragment_unknown_count == 0

    def test_frequent_neighbour_counts_when_threshold_is_off(self) -> None:
        tokens = _sentence(0, 0, ["one", "concept", "two", "three", "feast"])
        candidates = _run(
            tokens, {"feast": CEFRLevel.C1, "concept": CEFRLevel.B2},
            {**EASY, "feast": 3.9, "concept": 4.77}, threshold="off",
        )
        feast = next(c for c in candidates if c.lemma == "feast")
        assert feast.fragment_unknown_count == 1


@pytest.mark.unit
class TestAnalyzeTextSlangNormalization:
    def test_normalizer_called_with_cleaned_text(self) -> None:
        text_cleaner = MagicMock()
        text_cleaner.clean.return_value = "I wanna go"

        text_normalizer = MagicMock()
        text_normalizer.normalize.return_value = "I want to go"

        text_analyzer = MagicMock()
        text_analyzer.analyze.return_value = []

        cefr_classifier = MagicMock()
        frequency_provider = MagicMock()
        phrasal_verb_detector = MagicMock()

        use_case = AnalyzeTextUseCase(
            text_cleaner=text_cleaner,
            text_normalizer=text_normalizer,
            text_analyzer=text_analyzer,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
            phrasal_verb_detector=phrasal_verb_detector,
        )

        request = AnalyzeTextRequest(raw_text="I wanna go", user_level="A1")
        use_case.execute(request)

        text_normalizer.normalize.assert_called_once_with("I wanna go")
        text_analyzer.analyze.assert_called_once_with("I want to go")
