"""Unit tests for AddManualCandidateUseCase.

The use case runs the same enrichment pipeline as auto processing (lemma,
POS, CEFR, frequency) but bypasses the CEFR gate: anything the user picks
is always saved. The branches that matter:

- source-not-found guard
- phrasal-verb fast path (via PhrasalVerbDetector match)
- regular-word path with in-context token match
- fallback: surface form doesn't appear in context → re-analyse surface form alone
- final fallback: no token found anywhere → pos=X, tag=NN, lemma=surface_lower
- occurrence counting (case-insensitive, ≥1)
- cleaned_text vs raw_text preference
- CEFR UNKNOWN → cefr_level DTO field is None
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.add_manual_candidate import (
    AddManualCandidateUseCase,
)
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.entities.token_data import TokenData
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.services.phrasal_verb_detector import PhrasalVerbMatch
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus


def _token(
    index: int,
    text: str,
    lemma: str,
    *,
    pos: str = "NOUN",
    tag: str = "NN",
) -> TokenData:
    return TokenData(
        index=index,
        text=text,
        lemma=lemma,
        pos=pos,
        tag=tag,
        head_index=0,
        children_indices=(),
        is_punct=False,
        is_stop=False,
        is_alpha=True,
        is_propn=False,
        sent_index=0,
    )


def _source(
    *,
    raw: str = "procrastinate procrastinate today",
    cleaned: str | None = None,
) -> Source:
    return Source(
        id=1,
        raw_text=raw,
        cleaned_text=cleaned,
        status=SourceStatus.DONE,
        input_method=InputMethod.TEXT_PASTED,
        content_type=ContentType.TEXT,
    )


def _patch_classify_detailed(mock: MagicMock) -> MagicMock:
    """Wire classify_detailed to return CEFRBreakdown wrapping classify result."""
    original_classify = mock.classify

    def _detailed(lemma: str, tag: str) -> CEFRBreakdown:
        level = original_classify(lemma, tag)
        return CEFRBreakdown(
            final_level=level,
            decision_method="voting",
            priority_votes=[],
            votes=[],
        )

    mock.classify_detailed.side_effect = _detailed
    return mock


def _make_use_case(
    *,
    source_repo: MagicMock | None = None,
    candidate_repo: MagicMock | None = None,
    text_analyzer: MagicMock | None = None,
    cefr_classifier: MagicMock | None = None,
    frequency_provider: MagicMock | None = None,
    phrasal_verb_detector: MagicMock | None = None,
) -> AddManualCandidateUseCase:
    classifier = cefr_classifier or MagicMock()
    _patch_classify_detailed(classifier)
    return AddManualCandidateUseCase(
        source_repo=source_repo or MagicMock(),
        candidate_repo=candidate_repo or MagicMock(),
        text_analyzer=text_analyzer or MagicMock(),
        cefr_classifier=classifier,
        frequency_provider=frequency_provider or MagicMock(),
        phrasal_verb_detector=phrasal_verb_detector or MagicMock(),
    )


def _stored(candidate: StoredCandidate, new_id: int = 99) -> StoredCandidate:
    # Simulate repo assigning an id on save.
    return StoredCandidate(
        id=new_id,
        source_id=candidate.source_id,
        lemma=candidate.lemma,
        pos=candidate.pos,
        cefr_level=candidate.cefr_level,
        zipf_frequency=candidate.zipf_frequency,
        context_fragment=candidate.context_fragment,
        fragment_purity=candidate.fragment_purity,
        occurrences=candidate.occurrences,
        surface_form=candidate.surface_form,
        is_phrasal_verb=candidate.is_phrasal_verb,
        status=candidate.status,
    )


def _mock_repo_save() -> MagicMock:
    """Returns a candidate_repo mock whose create_batch echoes input with id set."""
    repo = MagicMock()

    def _create(candidates: list[StoredCandidate]) -> list[StoredCandidate]:
        return [_stored(c, new_id=100 + i) for i, c in enumerate(candidates)]

    repo.create_batch.side_effect = _create
    return repo


# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGuards:
    def test_raises_source_not_found_when_source_missing(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = None
        use_case = _make_use_case(source_repo=source_repo)

        with pytest.raises(SourceNotFoundError):
            use_case.execute(
                source_id=42,
                surface_form="word",
                context_fragment="word in context",
            )


@pytest.mark.unit
class TestRegularWordPath:
    def test_creates_candidate_with_in_context_token_match(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _source(
            raw="I procrastinate procrastinate today"
        )
        candidate_repo = _mock_repo_save()
        text_analyzer = MagicMock()
        text_analyzer.analyze.return_value = [
            _token(0, "I", "I", pos="PRON", tag="PRP"),
            _token(1, "procrastinate", "procrastinate", pos="VERB", tag="VB"),
            _token(2, "today", "today", pos="NOUN", tag="NN"),
        ]
        phrasal_verb_detector = MagicMock()
        phrasal_verb_detector.detect.return_value = []
        cefr_classifier = MagicMock()
        cefr_classifier.classify.return_value = CEFRLevel.C1
        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.return_value = 3.7

        use_case = _make_use_case(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1,
            surface_form="procrastinate",
            context_fragment="I procrastinate today",
        )

        assert dto.lemma == "procrastinate"
        assert dto.pos == "VERB"
        assert dto.cefr_level == "C1"
        assert dto.zipf_frequency == 3.7
        assert dto.is_sweet_spot is True  # 3.0 ≤ 3.7 ≤ 4.5
        assert dto.surface_form == "procrastinate"
        assert dto.is_phrasal_verb is False
        assert dto.occurrences == 2  # two occurrences in raw_text
        assert dto.fragment_purity == "clean"
        assert dto.status == CandidateStatus.PENDING.value
        cefr_classifier.classify.assert_called_once_with("procrastinate", "VB")
        frequency_provider.get_zipf_value.assert_called_once_with("procrastinate")

    def test_case_insensitive_match_and_lowercase_lemma(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _source(raw="Dolor sit dolor amet")
        candidate_repo = _mock_repo_save()
        text_analyzer = MagicMock()
        text_analyzer.analyze.return_value = [
            _token(0, "Dolor", "Dolor", pos="NOUN", tag="NN"),
            _token(1, "sit", "sit", pos="VERB", tag="VB"),
        ]
        phrasal_verb_detector = MagicMock()
        phrasal_verb_detector.detect.return_value = []
        cefr_classifier = MagicMock()
        cefr_classifier.classify.return_value = CEFRLevel.B2
        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.return_value = 5.0

        use_case = _make_use_case(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1,
            surface_form="dolor",
            context_fragment="Dolor sit",
        )

        assert dto.lemma == "dolor"  # lowercased
        assert dto.occurrences == 2

    def test_unknown_cefr_results_in_none_cefr_level(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _source(raw="word")
        candidate_repo = _mock_repo_save()
        text_analyzer = MagicMock()
        text_analyzer.analyze.return_value = [
            _token(0, "word", "word", pos="NOUN", tag="NN"),
        ]
        phrasal_verb_detector = MagicMock()
        phrasal_verb_detector.detect.return_value = []
        cefr_classifier = MagicMock()
        cefr_classifier.classify.return_value = CEFRLevel.UNKNOWN
        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.return_value = 5.5

        use_case = _make_use_case(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1, surface_form="word", context_fragment="word"
        )
        assert dto.cefr_level is None
        assert dto.is_sweet_spot is False  # 5.5 > 4.5

    def test_occurrences_at_least_one_when_not_in_source(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _source(raw="lorem ipsum")
        candidate_repo = _mock_repo_save()
        text_analyzer = MagicMock()
        text_analyzer.analyze.side_effect = [
            # First call: analyze context_fragment ("unknownword xyz") —
            # surface_form "unknownword" IS present as a token here, so the
            # regular-word branch finds it without falling back.
            [
                _token(0, "unknownword", "unknownword", pos="NOUN", tag="NN"),
                _token(1, "xyz", "xyz"),
            ],
        ]
        phrasal_verb_detector = MagicMock()
        phrasal_verb_detector.detect.return_value = []
        cefr_classifier = MagicMock()
        cefr_classifier.classify.return_value = CEFRLevel.UNKNOWN
        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.return_value = 5.5

        use_case = _make_use_case(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1,
            surface_form="unknownword",
            context_fragment="unknownword xyz",
        )
        assert dto.occurrences == 1  # raw text doesn't contain it → max(0, 1) = 1

    def test_uses_cleaned_text_when_available(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _source(
            raw="raw raw raw", cleaned="hello hello world"
        )
        candidate_repo = _mock_repo_save()
        text_analyzer = MagicMock()
        text_analyzer.analyze.return_value = [
            _token(0, "hello", "hello", pos="INTJ", tag="UH"),
            _token(1, "world", "world", pos="NOUN", tag="NN"),
        ]
        phrasal_verb_detector = MagicMock()
        phrasal_verb_detector.detect.return_value = []
        cefr_classifier = MagicMock()
        cefr_classifier.classify.return_value = CEFRLevel.A1
        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.return_value = 6.0

        use_case = _make_use_case(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1, surface_form="hello", context_fragment="hello world"
        )
        # "hello" appears twice in cleaned_text, 0 times in raw → should see 2.
        assert dto.occurrences == 2


@pytest.mark.unit
class TestFallbackToSurfaceFormAnalysis:
    def test_analyses_surface_form_alone_when_not_found_in_context(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _source(raw="lorem ipsum dolor")
        candidate_repo = _mock_repo_save()
        text_analyzer = MagicMock()
        # 1st analyze (context): no token matching "dolor"
        # 2nd analyze (surface_form alone): yields the token
        text_analyzer.analyze.side_effect = [
            [
                _token(0, "lorem", "lorem", pos="NOUN", tag="NN"),
                _token(1, "ipsum", "ipsum", pos="NOUN", tag="NN"),
            ],
            [_token(0, "dolor", "dolor", pos="NOUN", tag="NN")],
        ]
        phrasal_verb_detector = MagicMock()
        phrasal_verb_detector.detect.return_value = []
        cefr_classifier = MagicMock()
        cefr_classifier.classify.return_value = CEFRLevel.B1
        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.return_value = 3.2

        use_case = _make_use_case(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1,
            surface_form="dolor",
            context_fragment="lorem ipsum",
        )
        assert dto.lemma == "dolor"
        assert dto.pos == "NOUN"
        assert text_analyzer.analyze.call_count == 2

    def test_falls_back_to_defaults_when_no_token_anywhere(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _source(raw="something else")
        candidate_repo = _mock_repo_save()
        text_analyzer = MagicMock()
        # Both calls return empty (e.g. punctuation-only input).
        text_analyzer.analyze.side_effect = [[], []]
        phrasal_verb_detector = MagicMock()
        phrasal_verb_detector.detect.return_value = []
        cefr_classifier = MagicMock()
        cefr_classifier.classify.return_value = CEFRLevel.UNKNOWN
        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.return_value = 5.0

        use_case = _make_use_case(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1, surface_form="???", context_fragment="context"
        )
        assert dto.lemma == "???"  # surface_lower fallback
        assert dto.pos == "X"
        cefr_classifier.classify.assert_called_once_with("???", "NN")


@pytest.mark.unit
class TestPhrasalVerbPath:
    def test_match_uses_verb_token_tag_when_present(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _source(
            raw="I give up today give up"
        )
        candidate_repo = _mock_repo_save()
        text_analyzer = MagicMock()
        tokens = [
            _token(0, "I", "I", pos="PRON", tag="PRP"),
            _token(1, "give", "give", pos="VERB", tag="VBP"),
            _token(2, "up", "up", pos="ADP", tag="RP"),
            _token(3, "today", "today"),
        ]
        text_analyzer.analyze.return_value = tokens
        pv = PhrasalVerbMatch(
            verb_index=1,
            component_indices=(2,),
            lemma="give up",
            surface_form="give up",
        )
        phrasal_verb_detector = MagicMock()
        phrasal_verb_detector.detect.return_value = [pv]
        cefr_classifier = MagicMock()
        cefr_classifier.classify.return_value = CEFRLevel.B1
        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.return_value = 4.0

        use_case = _make_use_case(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1,
            surface_form="give up",
            context_fragment="I give up today",
        )
        assert dto.lemma == "give up"
        assert dto.pos == "VERB"
        assert dto.is_phrasal_verb is True
        assert dto.occurrences == 2
        # The verb token tag ("VBP") must have been passed to the classifier.
        cefr_classifier.classify.assert_called_once_with("give up", "VBP")

    def test_match_falls_back_to_VB_tag_when_verb_token_missing(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _source(raw="x")
        candidate_repo = _mock_repo_save()
        text_analyzer = MagicMock()
        tokens = [
            _token(0, "filler", "filler", pos="NOUN", tag="NN"),
        ]
        text_analyzer.analyze.return_value = tokens
        pv = PhrasalVerbMatch(
            verb_index=999,  # intentionally not in token_map
            component_indices=(1000,),
            lemma="give up",
            surface_form="give up",
        )
        phrasal_verb_detector = MagicMock()
        phrasal_verb_detector.detect.return_value = [pv]
        cefr_classifier = MagicMock()
        cefr_classifier.classify.return_value = CEFRLevel.B1
        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.return_value = 4.0

        use_case = _make_use_case(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        use_case.execute(
            source_id=1,
            surface_form="give up",
            context_fragment="give up",
        )
        cefr_classifier.classify.assert_called_once_with("give up", "VB")

    def test_pv_match_selected_by_case_insensitive_surface_form(self) -> None:
        """The match list is filtered by surface_form.lower() == surface_lower.
        We verify the lookup is case-insensitive."""
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _source(raw="x")
        candidate_repo = _mock_repo_save()
        text_analyzer = MagicMock()
        text_analyzer.analyze.return_value = [
            _token(0, "give", "give", pos="VERB", tag="VB"),
            _token(1, "UP", "up", pos="ADP", tag="RP"),
        ]
        pv = PhrasalVerbMatch(
            verb_index=0,
            component_indices=(1,),
            lemma="give up",
            surface_form="give UP",  # upper-case in source
        )
        phrasal_verb_detector = MagicMock()
        phrasal_verb_detector.detect.return_value = [pv]
        cefr_classifier = MagicMock()
        cefr_classifier.classify.return_value = CEFRLevel.B1
        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.return_value = 4.0

        use_case = _make_use_case(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1,
            surface_form="give up",  # lowercase query
            context_fragment="give UP",
        )
        assert dto.is_phrasal_verb is True
