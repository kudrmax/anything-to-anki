from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from backend.application.dto.analysis_dtos import (
    AnalyzeTextRequest,
    AnalyzeTextResponse,
    OccurrenceDTO,
    WordDTO,
)
from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.entities.token_data import TokenData
from backend.domain.ports.document_analyzer import AnalyzedDocument, DocumentAnalyzer
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.services.phrasal_verb_detector import PhrasalVerbMatch
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.frequency_band import FrequencyBand
from backend.domain.value_objects.user_knowledge import UserKnowledge
from backend.domain.value_objects.vocabulary import Vocabulary


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


class _LaidOutTokens(DocumentAnalyzer):
    """A one-paragraph document of the tokens, each placed where its text stands."""

    def __init__(self, tokens: list[TokenData]) -> None:
        placed: list[TokenData] = []
        text = ""
        for token in tokens:
            placed.append(replace(token, char_start=len(text)))
            text += token.text + (token.whitespace_after or " ")
        self.tokens = placed
        self.document = Document((
            Paragraph(lines=(Line(text.strip() or "-"),), mode=ParagraphMode.FLOW),
        ))

    def analyze(self, document: Document) -> AnalyzedDocument:
        return AnalyzedDocument(tokens=self.tokens, layout=DocumentLayout(document))


class _Analysis:
    def __init__(self, use_case: AnalyzeTextUseCase, analyzer: _LaidOutTokens) -> None:
        self._use_case = use_case
        self._phrasal_verb_detector = use_case._phrasal_verb_detector
        self.document = analyzer.document

    def execute(self, request: AnalyzeTextRequest) -> AnalyzeTextResponse:
        return self._use_case.execute(self.document, request)


def _create_use_case(
    tokens: list[TokenData] | None = None,
    cefr_map: dict[str, CEFRLevel] | None = None,
    freq_map: dict[str, float] | None = None,
) -> _Analysis:
    analyzer = _LaidOutTokens(tokens or [])

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

    use_case = AnalyzeTextUseCase(
        document_analyzer=analyzer,
        cefr_classifier=cefr_classifier,
        frequency_provider=frequency_provider,
        phrasal_verb_detector=phrasal_verb_detector,
    )
    return _Analysis(use_case, analyzer)


@pytest.mark.unit
class TestAnalyzeTextUseCase:
    def test_no_tokens_returns_empty(self) -> None:
        use_case = _create_use_case(tokens=[])
        request = AnalyzeTextRequest(user_level="B1")
        response = use_case.execute(request)
        assert response.words == []
        assert response.total_tokens == 0

    def test_filters_below_user_level(self) -> None:
        tokens = [_make_token(0, "happy", "happy")]
        use_case = _create_use_case(
            tokens=tokens,
            cefr_map={"happy": CEFRLevel.A1},
        )
        request = AnalyzeTextRequest(user_level="B1")
        response = use_case.execute(request)
        assert len(response.words) == 0

    def test_includes_above_user_level(self) -> None:
        tokens = [_make_token(0, "relentless", "relentless")]
        use_case = _create_use_case(
            tokens=tokens,
            cefr_map={"relentless": CEFRLevel.C1},
            freq_map={"relentless": 3.5},
        )
        request = AnalyzeTextRequest(user_level="B1")
        response = use_case.execute(request)
        assert len(response.words) == 1
        assert response.words[0].lemma == "relentless"
        assert response.words[0].cefr_level == "C1"

    def test_deduplicates_same_lemma(self) -> None:
        tokens = [
            _make_token(0, "pursue", "pursue", tag="VB"),
            _make_token(1, "pursuing", "pursue", tag="VBG"),
        ]
        use_case = _create_use_case(
            tokens=tokens,
            cefr_map={"pursue": CEFRLevel.B2},
            freq_map={"pursue": 4.0},
        )
        request = AnalyzeTextRequest(user_level="B1")
        response = use_case.execute(request)
        # Both have same (lemma, pos) = ("pursue", "NOUN"), should deduplicate
        assert len(response.words) == 1
        assert len(response.words[0].occurrences) == 2

    def test_both_candidates_returned(self) -> None:
        tokens = [
            _make_token(0, "ubiquitous", "ubiquitous"),
            _make_token(1, "pursuit", "pursuit"),
        ]
        use_case = _create_use_case(
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
        request = AnalyzeTextRequest(user_level="B1")
        response = use_case.execute(request)
        assert len(response.words) == 2
        lemmas = {c.lemma for c in response.words}
        assert lemmas == {"pursuit", "ubiquitous"}

    def test_filters_stop_words(self) -> None:
        tokens = [_make_token(0, "the", "the", is_stop=True)]
        use_case = _create_use_case(
            tokens=tokens,
            cefr_map={"the": CEFRLevel.C1},
        )
        request = AnalyzeTextRequest(user_level="B1")
        response = use_case.execute(request)
        assert len(response.words) == 0

    def test_phrase_words_are_read_from_the_phrase(self) -> None:
        tokens = [_make_token(0, "relentless", "relentless")]
        use_case = _create_use_case(
            tokens=tokens,
            cefr_map={"relentless": CEFRLevel.C1},
            freq_map={"relentless": 3.5},
        )
        request = AnalyzeTextRequest(user_level="B1")
        response = use_case.execute(request)
        candidate = _best(response.words[0])
        assert candidate.phrase.text == "relentless"
        assert candidate.phrase.target_text() == "relentless"
        assert [word.lemma for word in candidate.phrase.words] == ["relentless"]


def _best(word: WordDTO) -> OccurrenceDTO:
    """The phrase a card gets today: the best score, ties to the earliest."""
    return min(word.occurrences, key=lambda occurrence: occurrence.fragment_score)


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
    frequent_zipf: float | None = 4.5,
    unknown: frozenset[str] = frozenset(),
    learning: frozenset[str] = frozenset(),
) -> list[WordDTO]:
    use_case = _create_use_case(
        tokens=tokens,
        cefr_map=cefr_map,
        freq_map=freq_map or {},
    )
    request = AnalyzeTextRequest(
        user_level="B1", vocabulary=Vocabulary.of(known=known, unknown=unknown, learning=learning),
        frequent_word_zipf=frequent_zipf,
    )
    return use_case.execute(request).words


def _rare(candidate: WordDTO, frequent_zipf: float | None = 4.5) -> list[str]:
    knowledge = UserKnowledge(
        vocabulary=Vocabulary.of(known=set(), unknown=set()),
        user_level=CEFRLevel.B1,
        frequent_zipf=frequent_zipf,
    )
    other_words = _best(candidate).phrase.other_words()
    return [word.lemma for word in other_words if knowledge.is_new(word)]


EASY = {"one": 3.0, "two": 3.0, "three": 3.0, "four": 3.0, "five": 3.0, "six": 3.0}


@pytest.mark.unit
class TestAnalyzeTextKnownWords:
    def test_known_word_is_not_a_candidate(self) -> None:
        tokens = [_make_token(0, "divorced", "divorce", pos="VERB", tag="VBN")]
        candidates = _run(tokens, {"divorce": CEFRLevel.B2}, known=frozenset({"divorce"}))
        assert candidates == []

    def test_word_learned_elsewhere_is_not_a_candidate(self) -> None:
        tokens = [_make_token(0, "divorced", "divorce", pos="VERB", tag="VBN")]
        candidates = _run(tokens, {"divorce": CEFRLevel.B2}, learning=frozenset({"divorce"}))
        assert candidates == []

    def test_word_learned_elsewhere_but_marked_unknown_is_a_candidate(self) -> None:
        tokens = [_make_token(0, "divorced", "divorce", pos="VERB", tag="VBN")]
        candidates = _run(
            tokens, {"divorce": CEFRLevel.B2},
            learning=frozenset({"divorce"}), unknown=frozenset({"divorce"}),
        )
        assert [c.lemma for c in candidates] == ["divorce"]

    def test_known_phrasal_verb_is_not_a_candidate(self) -> None:
        tokens = [
            _make_token(0, "made", "make", pos="VERB", tag="VBD"),
            _make_token(1, "up", "up", pos="ADP", tag="RP"),
        ]
        use_case = _create_use_case(tokens=tokens)
        use_case._phrasal_verb_detector.detect.return_value = [  # type: ignore[attr-defined]
            PhrasalVerbMatch(
                verb_index=0, component_indices=(1,), lemma="make up", surface_form="made up",
            ),
        ]
        request = AnalyzeTextRequest(
            user_level="B1", vocabulary=Vocabulary.of(known={"make up"}, unknown=set()),
        )
        assert use_case.execute(request).words == []


@pytest.mark.unit
class TestAnalyzeTextOneCardPerWord:
    def test_same_word_as_different_parts_of_speech_is_one_candidate(self) -> None:
        tokens = [
            _make_token(0, "premium", "premium", pos="ADJ", tag="JJ"),
            _make_token(1, "premium", "premium", pos="NOUN", tag="NN"),
        ]
        candidates = _run(tokens, {"premium": CEFRLevel.B2}, {"premium": 4.3})
        assert len(candidates) == 1
        assert len(candidates[0].occurrences) == 2

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
        assert _best(feast).phrase.text == "four five six one feast"
        assert _rare(feast) == []

    def test_other_unknown_word_makes_phrase_dirty(self) -> None:
        tokens = _sentence(0, 0, ["one", "rival", "two", "three", "feast"])
        candidates = _run(
            tokens, {"feast": CEFRLevel.C1, "rival": CEFRLevel.C1},
            {**EASY, "feast": 3.9, "rival": 3.9},
        )
        feast = next(c for c in candidates if c.lemma == "feast")
        assert _rare(feast) == ["rival"]

    def test_known_neighbour_does_not_push_phrase_away(self) -> None:
        first = _sentence(0, 0, ["one", "rival", "two", "three", "feast"])
        second = _sentence(5, 1, ["four", "five", "six", "gale", "feast"])
        candidates = _run(
            first + second, {"feast": CEFRLevel.C1, "rival": CEFRLevel.C1, "gale": CEFRLevel.C1},
            {**EASY, "feast": 3.9, "rival": 3.9, "gale": 3.9}, known=frozenset({"rival"}),
        )
        feast = next(c for c in candidates if c.lemma == "feast")
        assert _best(feast).phrase.text == "one rival two three feast"

    def test_unknown_neighbour_pushes_phrase_away_even_if_easy(self) -> None:
        first = _sentence(0, 0, ["one", "two", "three", "four", "feast"])
        second = _sentence(5, 1, ["five", "six", "two", "three", "feast"])
        candidates = _run(
            first + second, {"feast": CEFRLevel.C1},
            {**EASY, "feast": 3.9}, unknown=frozenset({"one"}),
        )
        feast = next(c for c in candidates if c.lemma == "feast")
        assert _best(feast).phrase.text == "five six two three feast"

    def test_frequent_neighbour_is_not_counted_as_unknown(self) -> None:
        tokens = _sentence(0, 0, ["one", "concept", "two", "three", "feast"])
        candidates = _run(
            tokens, {"feast": CEFRLevel.C1, "concept": CEFRLevel.B2},
            {**EASY, "feast": 3.9, "concept": 4.77},
        )
        feast = next(c for c in candidates if c.lemma == "feast")
        assert _rare(feast) == []

    def test_frequent_neighbour_counts_when_threshold_is_off(self) -> None:
        tokens = _sentence(0, 0, ["one", "concept", "two", "three", "feast"])
        candidates = _run(
            tokens, {"feast": CEFRLevel.C1, "concept": CEFRLevel.B2},
            {**EASY, "feast": 3.9, "concept": 4.77}, frequent_zipf=None,
        )
        feast = next(c for c in candidates if c.lemma == "feast")
        assert _rare(feast, frequent_zipf=None) == ["concept"]


@pytest.mark.unit
class TestAnalyzeTextLemmaFixes:
    def test_lost_silent_e_is_restored(self) -> None:
        tokens = [_make_token(0, "hoping", "hop", pos="VERB", tag="VBG")]
        candidates = _run(
            tokens, {"hope": CEFRLevel.B2}, {"hop": 4.4, "hope": 5.44, "hoping": 4.67},
            frequent_zipf=None,
        )
        assert [c.lemma for c in candidates] == ["hope"]

    def test_doubled_consonant_keeps_the_short_stem(self) -> None:
        tokens = [_make_token(0, "hopping", "hop", pos="VERB", tag="VBG")]
        candidates = _run(
            tokens, {"hop": CEFRLevel.B2}, {"hop": 4.4, "hope": 5.44, "hopping": 3.43},
            frequent_zipf=None,
        )
        assert [c.lemma for c in candidates] == ["hop"]

    def test_stem_without_silent_e_spelling_is_kept(self) -> None:
        """'visiting' — 'visite' is only a rare typo."""
        tokens = [_make_token(0, "visiting", "visit", pos="VERB", tag="VBG")]
        candidates = _run(
            tokens, {"visit": CEFRLevel.B2}, {"visit": 5.0, "visite": 2.06, "visiting": 4.5},
            frequent_zipf=None,
        )
        assert [c.lemma for c in candidates] == ["visit"]

    def test_plural_only_noun_keeps_its_s(self) -> None:
        tokens = [_make_token(0, "pants", "pant", tag="NNS")]
        candidates = _run(tokens, {"pants": CEFRLevel.B2}, {"pant": 3.18, "pants": 4.48})
        assert [c.lemma for c in candidates] == ["pants"]

    def test_regular_plural_goes_to_singular(self) -> None:
        tokens = [_make_token(0, "glasses", "glass", tag="NNS")]
        candidates = _run(tokens, {"glass": CEFRLevel.B2}, {"glass": 4.85, "glasses": 4.34})
        assert [c.lemma for c in candidates] == ["glass"]


@pytest.mark.unit
class TestAnalyzeTextPositions:
    def test_phrase_and_split_target_are_placed_in_the_document(self) -> None:
        tokens = [
            replace(_make_token(0, "She", "she", pos="PRON"), whitespace_after=" "),
            replace(_make_token(1, "gave", "give", pos="VERB", tag="VBD"), whitespace_after=" "),
            replace(_make_token(2, "it", "it", pos="PRON"), whitespace_after=" "),
            replace(_make_token(3, "up", "up", pos="ADP", tag="RP"), whitespace_after=""),
        ]
        analysis = _create_use_case(tokens=tokens, freq_map={"give up": 3.0})
        analysis._phrasal_verb_detector.detect.return_value = [  # type: ignore[attr-defined]
            PhrasalVerbMatch(
                verb_index=1, component_indices=(3,), lemma="give up", surface_form="gave up",
            ),
        ]
        words = analysis.execute(AnalyzeTextRequest(user_level="B1")).words
        give_up = _best(next(c for c in words if c.lemma == "give up"))
        assert give_up.phrase.target_text() == "gave up"
        assert give_up.phrase_position is not None
        assert give_up.phrase_position.to_position() == DocumentPosition(0, 0, 0, 0, 14)
        assert give_up.phrase.text == "She gave it up"[
            give_up.phrase_position.start_char : give_up.phrase_position.end_char
        ]


def _classifier_by_tag(levels: dict[str, CEFRLevel]) -> MagicMock:
    classifier = MagicMock()
    classifier.classify_detailed.side_effect = lambda lemma, tag: CEFRBreakdown(
        final_level=levels.get(tag, CEFRLevel.A1),
        decision_method="voting",
        priority_votes=[],
        votes=[],
    )
    return classifier


def _analyze_with(
    tokens: list[TokenData], cefr_classifier: MagicMock,
) -> list[WordDTO]:
    analyzer = _LaidOutTokens(tokens)
    frequency_provider = MagicMock()
    frequency_provider.get_zipf_value.return_value = 3.0
    phrasal_verb_detector = MagicMock()
    phrasal_verb_detector.detect.return_value = []
    use_case = AnalyzeTextUseCase(
        document_analyzer=analyzer,
        cefr_classifier=cefr_classifier,
        frequency_provider=frequency_provider,
        phrasal_verb_detector=phrasal_verb_detector,
    )
    return use_case.execute(analyzer.document, AnalyzeTextRequest(user_level="B1")).words


@pytest.mark.unit
class TestAnalyzeTextEveryOccurrence:
    def test_every_occurrence_of_a_word_comes_with_its_phrase_and_score(self) -> None:
        first = _sentence(0, 0, ["one", "glare", "two"])
        second = _sentence(3, 1, ["three", "four", "glare"])
        words = _run(first + second, {"glare": CEFRLevel.C1}, {**EASY, "glare": 3.0})

        assert [w.lemma for w in words] == ["glare"]
        glare = words[0]
        assert [o.phrase.text for o in glare.occurrences] == [
            "one glare two", "three four glare",
        ]
        assert all(isinstance(o.fragment_score, float) for o in glare.occurrences)
        assert [o.phrase.target_text() for o in glare.occurrences] == ["glare", "glare"]

    def test_occurrence_key_is_where_the_target_starts_in_its_line(self) -> None:
        tokens = _sentence(0, 0, ["one", "glare", "two", "three", "glare"])
        words = _run(tokens, {"glare": CEFRLevel.C1}, {**EASY, "glare": 3.0})

        keys = [(o.key.block, o.key.line, o.key.char) for o in words[0].occurrences]
        assert keys == [(0, 0, 4), (0, 0, 20)]

    def test_key_of_a_split_target_is_its_first_word(self) -> None:
        tokens = [
            replace(_make_token(0, "She", "she", pos="PRON"), whitespace_after=" "),
            replace(_make_token(1, "gave", "give", pos="VERB", tag="VBD"), whitespace_after=" "),
            replace(_make_token(2, "it", "it", pos="PRON"), whitespace_after=" "),
            replace(_make_token(3, "up", "up", pos="ADP", tag="RP"), whitespace_after=""),
        ]
        analysis = _create_use_case(tokens=tokens, freq_map={"give up": 3.0})
        analysis._phrasal_verb_detector.detect.return_value = [  # type: ignore[attr-defined]
            PhrasalVerbMatch(
                verb_index=1, component_indices=(3,), lemma="give up", surface_form="gave up",
            ),
        ]
        words = analysis.execute(AnalyzeTextRequest(user_level="B1")).words
        give_up = next(w for w in words if w.lemma == "give up")
        assert give_up.occurrences[0].key.to_key() == OccurrenceKey(block=0, line=0, char=4)

    def test_key_counts_from_the_start_of_the_line_the_target_is_on(self) -> None:
        document = Document((Paragraph(
            lines=(Line("one two"), Line("three glare")), mode=ParagraphMode.FLOW,
        ),))
        tokens = [
            replace(_make_token(i, text, text, sent_index=0), char_start=start)
            for i, (text, start) in enumerate(
                [("one", 0), ("two", 4), ("three", 8), ("glare", 14)],
            )
        ]

        class _Fixed(DocumentAnalyzer):
            def analyze(self, document: Document) -> AnalyzedDocument:
                return AnalyzedDocument(tokens=tokens, layout=DocumentLayout(document))

        frequency_provider = MagicMock()
        frequency_provider.get_zipf_value.side_effect = lambda lemma: (
            3.0 if lemma == "glare" else 6.0
        )
        phrasal_verb_detector = MagicMock()
        phrasal_verb_detector.detect.return_value = []
        cefr_classifier = MagicMock()
        cefr_classifier.classify_detailed.side_effect = lambda lemma, tag: CEFRBreakdown(
            final_level=CEFRLevel.C1 if lemma == "glare" else CEFRLevel.A1,
            decision_method="voting", priority_votes=[], votes=[],
        )
        use_case = AnalyzeTextUseCase(
            document_analyzer=_Fixed(),
            cefr_classifier=cefr_classifier,
            frequency_provider=frequency_provider,
            phrasal_verb_detector=phrasal_verb_detector,
        )
        words = use_case.execute(document, AnalyzeTextRequest(user_level="B1")).words
        glare = next(w for w in words if w.lemma == "glare")
        assert glare.occurrences[0].key.to_key() == OccurrenceKey(block=0, line=1, char=6)


@pytest.mark.unit
class TestAnalyzeTextWordData:
    GLARES = (
        ("glare", "NOUN", "NN"),
        ("glare", "VERB", "VB"),
        ("glare", "NOUN", "NN"),
    )

    def _tokens(self, forms: tuple[tuple[str, str, str], ...]) -> list[TokenData]:
        return [
            replace(
                _make_token(i, text, "glare", pos=pos, tag=tag, sent_index=i),
                whitespace_after=" ",
            )
            for i, (text, pos, tag) in enumerate(forms)
        ]

    def test_part_of_speech_and_level_come_from_the_most_frequent_tag(self) -> None:
        levels = {"NN": CEFRLevel.C1, "VB": CEFRLevel.A1}
        words = _analyze_with(self._tokens(self.GLARES), _classifier_by_tag(levels))

        assert len(words) == 1
        assert words[0].pos == "NOUN"
        assert words[0].cefr_level == "C1"
        assert len(words[0].occurrences) == 3

    def test_word_data_does_not_depend_on_the_order_of_occurrences(self) -> None:
        levels = {"NN": CEFRLevel.C1, "VB": CEFRLevel.B2}
        forward = _analyze_with(self._tokens(self.GLARES), _classifier_by_tag(levels))
        backward = _analyze_with(
            self._tokens(tuple(reversed(self.GLARES))), _classifier_by_tag(levels),
        )
        tied = (("glare", "VERB", "VB"), ("glare", "NOUN", "NN"))
        tied_back = tuple(reversed(tied))

        assert (forward[0].pos, forward[0].cefr_level) == ("NOUN", "C1")
        assert (backward[0].pos, backward[0].cefr_level) == ("NOUN", "C1")
        first = _analyze_with(self._tokens(tied), _classifier_by_tag(levels))
        second = _analyze_with(self._tokens(tied_back), _classifier_by_tag(levels))
        assert (first[0].pos, first[0].cefr_level) == (second[0].pos, second[0].cefr_level)

    def test_level_filter_is_applied_to_the_word_once(self) -> None:
        levels = {"NN": CEFRLevel.A1, "VB": CEFRLevel.C1}
        assert _analyze_with(self._tokens(self.GLARES), _classifier_by_tag(levels)) == []
