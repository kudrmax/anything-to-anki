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

from contextlib import contextmanager
from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.candidate_dtos import SelectionDTO
from backend.application.dto.source_dtos import CardDTO, card_to_dto
from backend.application.use_cases.add_manual_candidate import (
    AddManualCandidateUseCase,
)
from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.entities.token_data import TokenData
from backend.domain.exceptions import (
    InvalidPhraseError,
    SourceNotFoundError,
    TargetNotInPhraseError,
)
from backend.domain.ports.unit_of_work import UnitOfWork
from backend.domain.services.phrasal_verb_detector import PhrasalVerbMatch
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.review_card import ReviewCard
from backend.domain.value_objects.source_status import SourceStatus

from tests.candidate_sorter_support import section_stamper
from tests.card_support import CARD_SOURCE, context
from tests.lock_support import free_lock
from tests.phrase_support import phrase

if TYPE_CHECKING:
    from collections.abc import Iterator

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


def _picked(selected: str, surface: str) -> list[int]:
    """Numbers of the words of `surface` where they first stand together in the selection."""
    found = phrase(selected.strip())
    words = [found.word_text(i).lower() for i in range(len(found.words))]
    wanted = surface.lower().split()
    for first in range(len(words) - len(wanted) + 1):
        if words[first:first + len(wanted)] == wanted:
            return list(range(first, first + len(wanted)))
    return []


def _read_picked(text: str, picked: list[int]) -> Phrase:
    whole = phrase(text)
    if not picked or any(not 0 <= i < len(whole.words) for i in picked):
        raise TargetNotInPhraseError()
    return whole.with_target(tuple(picked))


def _phrase_reader() -> MagicMock:
    reader = MagicMock()
    reader.read_picked.side_effect = _read_picked
    return reader


def _saved(candidate_repo: MagicMock) -> StoredCandidate:
    """The new word as stored, with the id its phrase points at."""
    (word,) = candidate_repo.add_word.call_args[0]
    assert isinstance(word, StoredCandidate)
    return replace(word, id=_added(candidate_repo).candidate_id)


def _added(candidate_repo: MagicMock) -> Occurrence:
    """The phrase the use case added."""
    (occurrence,) = candidate_repo.occurrences.add.call_args[0]
    assert isinstance(occurrence, Occurrence)
    return occurrence


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
    unit_of_work: UnitOfWork | None = None,
) -> AddManualCandidateUseCase:
    classifier = cefr_classifier or MagicMock()
    _patch_classify_detailed(classifier)
    repo = candidate_repo or MagicMock()
    return AddManualCandidateUseCase(
        source_repo=source_repo or MagicMock(),
        document_repo=_documents(document_text),
        candidate_repo=repo,
        occurrence_repo=repo.occurrences,
        text_analyzer=text_analyzer or MagicMock(),
        cefr_classifier=classifier,
        frequency_provider=frequency_provider or MagicMock(),
        phrasal_verb_detector=phrasal_verb_detector or MagicMock(),
        phrase_reader=_phrase_reader(),
        stamper=section_stamper(MagicMock()),
        lock=free_lock(),
        card_views=_card_views(repo),
        decide_phrase=MagicMock(),
        unit_of_work=unit_of_work or MagicMock(),
    )


class _RecordingUnitOfWork(UnitOfWork):
    """Says whether a write transaction is open."""

    def __init__(self) -> None:
        self.open = False

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    @contextmanager
    def write(self) -> Iterator[None]:
        self.open = True
        try:
            yield
        finally:
            self.open = False


NEW_WORD_ID = 100
NEW_PHRASE_ID = 200


def _card_views(repo: MagicMock) -> MagicMock:
    """Answers with the card of the phrase the use case added."""
    views = MagicMock()

    def one(phrase_id: int) -> CardDTO:
        (added,) = repo.occurrences.add.call_args[0]
        shown = replace(added, id=phrase_id)
        return card_to_dto(ReviewCard(
            word=_saved(repo), occurrence=shown, context=context(_saved(repo), shown),
        ), CARD_SOURCE)

    views.one.side_effect = one
    return views


def _mock_repo_save() -> MagicMock:
    """A candidate_repo mock storing one new word; `.occurrences` stores its phrase."""
    repo = MagicMock()
    repo.word_id.return_value = None
    repo.add_word.return_value = NEW_WORD_ID
    repo.occurrences.add.side_effect = lambda occurrence: replace(occurrence, id=NEW_PHRASE_ID)
    repo.get_by_id.side_effect = lambda _word_id: _saved(repo)
    return repo


# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_word_and_its_phrase_are_written_in_one_write_transaction() -> None:
    source_repo = MagicMock()
    source_repo.get_by_id.return_value = _source()
    candidate_repo = _mock_repo_save()
    unit_of_work = _RecordingUnitOfWork()
    written_inside: list[bool] = []
    add = candidate_repo.occurrences.add.side_effect
    candidate_repo.occurrences.add.side_effect = lambda occ: (
        written_inside.append(unit_of_work.open) or add(occ)
    )
    text_analyzer = MagicMock()
    text_analyzer.analyze.return_value = [_token(0, "word", "word", pos="NOUN", tag="NN")]
    detector = MagicMock()
    detector.detect.return_value = []
    frequency = MagicMock()
    frequency.get_zipf_value.return_value = 3.7
    classifier = MagicMock()
    classifier.classify.return_value = CEFRLevel.C1
    use_case = _make_use_case(
        source_repo=source_repo, candidate_repo=candidate_repo, text_analyzer=text_analyzer,
        phrasal_verb_detector=detector, frequency_provider=frequency,
        cefr_classifier=classifier, unit_of_work=unit_of_work,
    )

    use_case.execute(
        source_id=1,
        target_words=_picked("word in context", "word"),
        selection=_select("word in context", "word in context"),
    )

    assert written_inside == [True]
    assert not unit_of_work.open


@pytest.mark.unit
class TestGuards:
    def test_raises_source_not_found_when_source_missing(self) -> None:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = None
        use_case = _make_use_case(source_repo=source_repo)

        with pytest.raises(SourceNotFoundError):
            use_case.execute(
                source_id=42,
                target_words=_picked("word in context", "word"),
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
            target_words=_picked("I procrastinate today", "procrastinate"),
            selection=_select(text, "I procrastinate today"),
        )

        assert dto.lemma == "procrastinate"
        assert dto.pos == "VERB"
        assert dto.cefr_level == "C1"
        assert dto.zipf_frequency == 3.7
        assert dto.is_sweet_spot is True  # 3.0 ≤ 3.7 ≤ 4.5
        assert _added(candidate_repo).phrase.target_text() == "procrastinate"
        assert dto.is_phrasal_verb is False
        assert dto.occurrences == 2  # two occurrences in the document
        assert dto.shown.status == "new"
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
            target_words=_picked("Dolor sit", "dolor"),
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
            source_id=1,
            target_words=_picked("word", "word"),
            selection=_select(text, "word"),
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
            target_words=_picked("unknownword xyz", "unknownword"),
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
            source_id=1,
            target_words=_picked("hello world", "hello"),
            selection=_select(text, "hello world"),
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
                target_words=_picked("lorem ipsum", "dolor"),
                selection=_select("lorem ipsum dolor", "lorem ipsum"),
            )
        candidate_repo.add_word.assert_not_called()

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
            target_words=_picked(" Dolor  sit amet. "[:-1], "dolor sit"),
            selection=_select("It was Dolor  sit amet.", " Dolor  sit amet. "[:-1]),
        )

        saved = _added(candidate_repo)
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
            target_words=_picked("lorem ipsum dolor", "dolor"),
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
            source_id=1,
            target_words=_picked("zzz in context", "zzz"),
            selection=_select(text, "zzz in context"),
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
            target_words=_picked("I give up today", "give up"),
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
            target_words=_picked("give UP", "give up"),
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
            target_words=_picked("give UP", "give up"),  # lowercase query
            selection=_select(text, "give UP"),
        )
        assert dto.is_phrasal_verb is True
