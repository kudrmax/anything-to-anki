"""Regression baseline for the 22 user-marked 'bad fragment' candidates from
HPMOR (source 1) and 'Evil Morty' lyrics (source 2).

Runs the full real ``AnalyzeTextUseCase`` pipeline (real spaCy, real
``BoundaryCleaner``) over the original full source texts and asserts the
fragment for each marked target lemma.

Baseline (assert ==): expected values are exactly what the pipeline produces
today. Any change that *changes* one of these values must update the expected
text — that's the regression signal. The former "wave 2 wishlist" cases
(conclusion, need) were fixed by preferring whole clauses over cut pieces and
now live in the baseline.

Source texts live in ``backend/tests/integration/fixtures/`` and are
self-contained — no DB dependency.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.application.dto.analysis_dtos import AnalyzeTextRequest
from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
from backend.infrastructure.adapters.json_phrasal_verb_dictionary import (
    JsonPhrasalVerbDictionary,
)
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner
from backend.infrastructure.adapters.slang_normalizer import SlangNormalizer
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer
from backend.infrastructure.adapters.wordfreq_frequency_provider import (
    WordfreqFrequencyProvider,
)

from tests.integration.dict_cache_support import make_voting_classifier

FIXTURES = Path(__file__).parent / "fixtures"
HPMOR = (FIXTURES / "hpmor_excerpt.txt").read_text()
LYRICS = (FIXTURES / "evil_morty_lyrics.txt").read_text()
USER_LEVEL = "A1"  # matches the level used when the source was originally analyzed


pytestmark = pytest.mark.integration




@pytest.fixture(scope="module")
def use_case() -> AnalyzeTextUseCase:
    return AnalyzeTextUseCase(
        text_cleaner=RegexTextCleaner(),
        text_normalizer=SlangNormalizer(),
        text_analyzer=SpaCyTextAnalyzer(),
        cefr_classifier=make_voting_classifier(),
        frequency_provider=WordfreqFrequencyProvider(),
        phrasal_verb_detector=PhrasalVerbDetector(JsonPhrasalVerbDictionary()),
    )


@pytest.fixture(scope="module")
def hpmor_fragments(use_case: AnalyzeTextUseCase) -> dict[str, str]:
    """lemma → context_fragment mapping for the full HPMOR excerpt."""
    resp = use_case.execute(AnalyzeTextRequest(raw_text=HPMOR, user_level=USER_LEVEL))
    return {c.lemma.lower(): c.context_fragment for c in resp.candidates}


@pytest.fixture(scope="module")
def lyrics_fragments(use_case: AnalyzeTextUseCase) -> dict[str, str]:
    """lemma → context_fragment mapping for the full Evil Morty lyrics."""
    resp = use_case.execute(AnalyzeTextRequest(raw_text=LYRICS, user_level=USER_LEVEL))
    return {c.lemma.lower(): c.context_fragment for c in resp.candidates}


# ---------------------------------------------------------------------------
# Wave 1 baseline — frozen exact-match expectations.
# Format: (test_id, lemma, expected_fragment)
# Update only when a wave intentionally changes the value.
# ---------------------------------------------------------------------------

WAVE_1_HPMOR: list[tuple[str, str, str]] = [
    ("45_look_at", "look at", "you just have to look at the world"),
    (
        "86_disclaimer",
        "disclaimer",
        "Disclaimer: J. K. Rowling owns Harry Potter",
    ),
    (
        "138_individually",
        "individually",
        "whose episodes are individually plotted",
    ),
    (
        "201_serial",
        "serial",
        "the story is that of serial fiction, i.e.",
    ),
    (
        "288_arbiter",
        "arbiter",
        "the final arbiter is observation - that you just have to look at the world",
    ),
    (
        "305_plot",
        "plot",
        "whose episodes are individually plotted",
    ),
    (
        "318_argument",
        "argument",
        "I can't win arguments with you",
    ),
    (
        "348_require",
        "require",
        "philosophers say a great deal about what science absolutely requires",
    ),
    # "correct" removed: Oxford 5000 classifies it as A1 (below B1 user level),
    # so it no longer passes the candidate filter.
    (
        "456_single",
        "single",
        "This is not a strict single-point-of-departure fic",
    ),
    (
        "474_own",
        "own",
        "no one owns the methods of rationality.",
    ),
    (
        "289_fic",
        "fic",
        "I've heard for this fic",
    ),
    (
        "394_consider",
        "consider",
        "The Professor considers shouting to be uncivilised.",
    ),
    (
        "235_conclusion",
        "conclusion",
        "with an overall arc building to a final conclusion.",
    ),
    (
        "477_need",
        "need",
        "there's no need to finish reading it all",
    ),
]

WAVE_1_LYRICS: list[tuple[str, str, str]] = [
    ("485_answer_to", "answer to", "I answer to nobody, Rick"),
    ("509_dimension", "dimension", "Did I mention ending Ricks of all dimensions"),
    ("521_genius", "genius", "that prick had tried forming me\nInto a genius"),
    (
        "486_believe_in",
        "believe in",
        "believe in this Citadel to the Ricks",
    ),
    (
        "525_defame",
        "defame",
        "Defamed by the fake news as a joke\nJuggling Rick don\u2019t know I\u2019ma go\n"
        "For their throats",
    ),
    (
        "554_cause",
        "cause",
        "Cause he never heard me say\n\u201cah geez",
    ),
]


@pytest.mark.integration
class TestWave1BaselineHPMOR:
    """Wave 1 fixed these — they must keep working in all future waves."""

    @pytest.mark.parametrize(
        ("lemma", "expected"),
        [(lemma, expected) for _, lemma, expected in WAVE_1_HPMOR],
        ids=[tid for tid, _, _ in WAVE_1_HPMOR],
    )
    def test_fragment(
        self, hpmor_fragments: dict[str, str], lemma: str, expected: str
    ) -> None:
        actual = hpmor_fragments.get(lemma)
        assert actual is not None, (
            f"lemma {lemma!r} disappeared from candidates — pipeline regression"
        )
        assert actual == expected


@pytest.mark.integration
class TestWave1BaselineLyrics:
    @pytest.mark.parametrize(
        ("lemma", "expected"),
        [(lemma, expected) for _, lemma, expected in WAVE_1_LYRICS],
        ids=[tid for tid, _, _ in WAVE_1_LYRICS],
    )
    def test_fragment(
        self, lyrics_fragments: dict[str, str], lemma: str, expected: str
    ) -> None:
        actual = lyrics_fragments.get(lemma)
        assert actual is not None, (
            f"lemma {lemma!r} disappeared from candidates — pipeline regression"
        )
        assert actual == expected
