"""Unit tests for AddManualCandidateUseCase.

The use case runs the same enrichment pipeline as auto processing (lemma,
POS, CEFR, frequency) but bypasses the CEFR gate: anything the user picks
is always saved. The branches that matter:

- source-not-found guard
- phrasal-verb fast path (via PhrasalVerbDetector match)
- regular-word path with in-context token match
- fallback: surface form doesn't appear in context → re-analyse surface form alone
- final fallback: no token found anywhere → pos=X, tag=NN, lemma=surface_lower
- a target that is not among the words of the selected phrase is refused
- occurrence counting in the document (case-insensitive, ≥1)
- the phrase is the selected piece of the document, the target the picked words in it
- CEFR UNKNOWN → cefr_level DTO field is None
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.candidate_dtos import SelectionDTO
from backend.application.use_cases.add_manual_candidate import (
    AddManualCandidateUseCase,
)
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.entities.token_data import TokenData
from backend.domain.exceptions import (
    InvalidPhraseError,
    SourceNotFoundError,
    TargetNotInPhraseError,
)
from backend.domain.services.phrasal_verb_detector import PhrasalVerbMatch
from backend.domain.services.phrase_building import target_by_lemma
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_status import SourceStatus

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase


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


def _source() -> Source:
    return Source(id=1, status=SourceStatus.DONE, format=Format.PLAIN, kind=Kind.TEXT)


def _documents(text: str) -> MagicMock:
    """A source whose document is one paragraph of `text`."""
    repo = MagicMock()
    repo.get.return_value = Document((Paragraph((Line(text),), ParagraphMode.FLOW),))
    return repo


def _select(text: str, phrase: str) -> SelectionDTO:
    start = text.index(phrase)
    return SelectionDTO(
        start_block=0, start_line=0, start_char=start,
        end_block=0, end_line=0, end_char=start + len(phrase),
    )


def _read_for(text: str, lemma: str) -> Phrase:
    found = phrase(text, lemma)
    if not target_by_lemma(found.words, text, lemma):
        raise TargetNotInPhraseError()
    return found


def _phrase_reader() -> MagicMock:
    reader = MagicMock()
    reader.read_for.side_effect = _read_for
    return reader


def _saved(candidate_repo: MagicMock) -> StoredCandidate:
    (saved,) = candidate_repo.create_batch.call_args[0][0]
    assert isinstance(saved, StoredCandidate)
    return saved


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
    document_text: str = "word in context",
    candidate_repo: MagicMock | None = None,
    text_analyzer: MagicMock | None = None,
    cefr_classifier: MagicMock | None = None,
    frequency_provider: MagicMock | None = None,
    phrasal_verb_detector: MagicMock | None = None,
    review_status: MagicMock | None = None,
) -> AddManualCandidateUseCase:
    classifier = cefr_classifier or MagicMock()
    _patch_classify_detailed(classifier)
    return AddManualCandidateUseCase(
        source_repo=source_repo or MagicMock(),
        document_repo=_documents(document_text),
        candidate_repo=candidate_repo or MagicMock(),
        text_analyzer=text_analyzer or MagicMock(),
        cefr_classifier=classifier,
        frequency_provider=frequency_provider or MagicMock(),
        phrasal_verb_detector=phrasal_verb_detector or MagicMock(),
        review_status=review_status or MagicMock(),
        phrase_reader=_phrase_reader(),
    )


def _stored(candidate: StoredCandidate, new_id: int = 99) -> StoredCandidate:
    # Simulate repo assigning an id on save.
    return replace(candidate, id=new_id)


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
                selection=_select("word in context", "word in context"),
            )


@pytest.mark.unit
class TestRegularWordPath:
    def test_creates_candidate_with_in_context_token_match(self) -> None:
        source_repo = MagicMock()
        text = "I procrastinate today. Procrastinate!"
        source_repo.get_by_id.return_value = _source()
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

        review_status = MagicMock()
        use_case = _make_use_case(
            source_repo=source_repo,
            document_text=text,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
            review_status=review_status,
        )
        dto = use_case.execute(
            source_id=1,
            surface_form="procrastinate",
            selection=_select(text, "I procrastinate today"),
        )

        review_status.refresh.assert_called_once_with(1)
        assert dto.lemma == "procrastinate"
        assert dto.pos == "VERB"
        assert dto.cefr_level == "C1"
        assert dto.zipf_frequency == 3.7
        assert dto.is_sweet_spot is True  # 3.0 ≤ 3.7 ≤ 4.5
        assert _saved(candidate_repo).phrase.target_text() == "procrastinate"
        assert dto.is_phrasal_verb is False
        assert dto.occurrences == 2  # two occurrences in the document
        assert dto.status == CandidateStatus.PENDING.value
        cefr_classifier.classify.assert_called_once_with("procrastinate", "VB")
        frequency_provider.get_zipf_value.assert_called_once_with("procrastinate")

    def test_case_insensitive_match_and_lowercase_lemma(self) -> None:
        source_repo = MagicMock()
        text = "Dolor sit dolor amet"
        source_repo.get_by_id.return_value = _source()
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
            document_text=text,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1,
            surface_form="dolor",
            selection=_select(text, "Dolor sit"),
        )

        assert dto.lemma == "dolor"  # lowercased
        assert dto.occurrences == 2

    def test_unknown_cefr_results_in_none_cefr_level(self) -> None:
        source_repo = MagicMock()
        text = "word"
        source_repo.get_by_id.return_value = _source()
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
            document_text=text,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1, surface_form="word", selection=_select(text, "word")
        )
        assert dto.cefr_level is None
        assert dto.is_sweet_spot is False  # 5.5 > 4.5

    def test_occurrences_at_least_one_when_not_in_source(self) -> None:
        source_repo = MagicMock()
        text = "lorem ipsum unknownword xyz"
        source_repo.get_by_id.return_value = _source()
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
            document_text=text,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1,
            surface_form="unknownword",
            selection=_select(text, "unknownword xyz"),
        )
        assert dto.occurrences == 1  # raw text doesn't contain it → max(0, 1) = 1

    def test_counts_occurrences_in_the_document(self) -> None:
        source_repo = MagicMock()
        text = "hello hello world"
        source_repo.get_by_id.return_value = _source()
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
            document_text=text,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1, surface_form="hello", selection=_select(text, "hello world")
        )
        assert dto.occurrences == 2


@pytest.mark.unit
class TestSelection:
    def test_target_outside_the_selected_phrase_is_rejected(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _source()
        candidate_repo = MagicMock()
        use_case = _make_use_case(
            source_repo=source_repo,
            document_text="lorem ipsum dolor",
            candidate_repo=candidate_repo,
        )

        with pytest.raises(InvalidPhraseError):
            use_case.execute(
                source_id=1,
                surface_form="dolor",
                selection=_select("lorem ipsum dolor", "lorem ipsum"),
            )
        candidate_repo.create_batch.assert_not_called()

    def test_phrase_and_target_are_placed_in_the_document(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _source()
        candidate_repo = _mock_repo_save()
        text_analyzer = MagicMock()
        text_analyzer.analyze.return_value = [_token(0, "Dolor", "dolor")]
        cefr_classifier = MagicMock()
        cefr_classifier.classify.return_value = CEFRLevel.B2
        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.return_value = 3.0
        use_case = _make_use_case(
            source_repo=source_repo,
            document_text="It was Dolor  sit amet.",
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )

        use_case.execute(
            source_id=1,
            surface_form="dolor sit",
            selection=_select("It was Dolor  sit amet.", " Dolor  sit amet. "[:-1]),
        )

        saved = _saved(candidate_repo)
        assert saved.source_phrase.text == "Dolor  sit amet."
        assert saved.phrase_position == DocumentPosition(0, 0, 7, 0, 23)
        assert saved.source_phrase.target == (0, 1)
        assert saved.source_phrase.runs(saved.source_phrase.target) == [(0, 10)]


@pytest.mark.unit
class TestFallbackToSurfaceFormAnalysis:
    def test_analyses_surface_form_alone_when_not_found_in_context(self) -> None:
        source_repo = MagicMock()
        text = "lorem ipsum dolor"
        source_repo.get_by_id.return_value = _source()
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
            document_text=text,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1,
            surface_form="dolor",
            selection=_select(text, "lorem ipsum dolor"),
        )
        assert dto.lemma == "dolor"
        assert dto.pos == "NOUN"
        assert text_analyzer.analyze.call_count == 2

    def test_falls_back_to_defaults_when_no_token_anywhere(self) -> None:
        source_repo = MagicMock()
        text = "say zzz in context"
        source_repo.get_by_id.return_value = _source()
        candidate_repo = _mock_repo_save()
        text_analyzer = MagicMock()
        # The analyser finds nothing, neither in the phrase nor in the target alone.
        text_analyzer.analyze.side_effect = [[], []]
        phrasal_verb_detector = MagicMock()
        phrasal_verb_detector.detect.return_value = []
        cefr_classifier = MagicMock()
        cefr_classifier.classify.return_value = CEFRLevel.UNKNOWN
        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.return_value = 5.0

        use_case = _make_use_case(
            source_repo=source_repo,
            document_text=text,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1, surface_form="zzz", selection=_select(text, "zzz in context")
        )
        assert dto.lemma == "zzz"  # surface_lower fallback
        assert dto.pos == "X"
        cefr_classifier.classify.assert_called_once_with("zzz", "NN")


@pytest.mark.unit
class TestPhrasalVerbPath:
    def test_match_uses_verb_token_tag_when_present(self) -> None:
        source_repo = MagicMock()
        text = "I give up today give up"
        source_repo.get_by_id.return_value = _source()
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
            document_text=text,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1,
            surface_form="give up",
            selection=_select(text, "I give up today"),
        )
        assert dto.lemma == "give up"
        assert dto.pos == "VERB"
        assert dto.is_phrasal_verb is True
        assert dto.occurrences == 2
        # The verb token tag ("VBP") must have been passed to the classifier.
        cefr_classifier.classify.assert_called_once_with("give up", "VBP")

    def test_match_falls_back_to_vb_tag_when_verb_token_missing(self) -> None:
        source_repo = MagicMock()
        text = "never give UP"
        source_repo.get_by_id.return_value = _source()
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
            document_text=text,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        use_case.execute(
            source_id=1,
            surface_form="give up",
            selection=_select(text, "give UP"),
        )
        cefr_classifier.classify.assert_called_once_with("give up", "VB")

    def test_pv_match_selected_by_case_insensitive_surface_form(self) -> None:
        """The match list is filtered by surface_form.lower() == surface_lower.
        We verify the lookup is case-insensitive."""
        source_repo = MagicMock()
        text = "never give UP"
        source_repo.get_by_id.return_value = _source()
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
            document_text=text,
            candidate_repo=candidate_repo,
            text_analyzer=text_analyzer,
            phrasal_verb_detector=phrasal_verb_detector,
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
        )
        dto = use_case.execute(
            source_id=1,
            surface_form="give up",  # lowercase query
            selection=_select(text, "give UP"),
        )
        assert dto.is_phrasal_verb is True
