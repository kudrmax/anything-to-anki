"""Regression baseline for the 22 user-marked 'bad fragment' candidates from
HPMOR (source 1) and 'Evil Morty' lyrics (source 2).

Runs the full real ``AnalyzeTextUseCase`` pipeline (real spaCy, real
``BoundaryCleaner``) over the original full source texts and asserts the
fragment for each marked target lemma.

Two kinds of cases:

1. **Wave 1 baseline (assert ==).** Frozen as of the Wave 1 verification run.
   Expected values are exactly what the pipeline produces today. Any future
   wave that *changes* one of these values must update the expected text —
   that's the regression signal.

2. **Wave 2 wishlist (xfail strict).** Cases that Wave 1 cannot fully fix
   (need extension, not trim). Marked ``xfail(strict=True)``: when a future
   wave fixes them, the test will go XPASS → FAIL, forcing us to update the
   fixture and lock the new behavior.

Source texts live in ``backend/tests/integration/fixtures/`` and are
self-contained — no DB dependency.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.application.dto.analysis_dtos import AnalyzeTextRequest
from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.infrastructure.adapters.cambridge.cefr_source import CambridgeCEFRSource
from backend.infrastructure.adapters.cambridge.parser import parse_cambridge_jsonl
from backend.infrastructure.adapters.cefrpy_cefr_source import CefrpyCEFRSource
from backend.infrastructure.adapters.efllex_cefr_source import EFLLexCEFRSource
from backend.infrastructure.adapters.json_phrasal_verb_dictionary import (
    JsonPhrasalVerbDictionary,
)
from backend.infrastructure.adapters.kelly_cefr_source import KellyCEFRSource
from backend.infrastructure.adapters.oxford_cefr_source import OxfordCEFRSource
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer
from backend.infrastructure.adapters.wordfreq_frequency_provider import (
    WordfreqFrequencyProvider,
)

FIXTURES = Path(__file__).parent / "fixtures"
HPMOR = (FIXTURES / "hpmor_excerpt.txt").read_text()
LYRICS = (FIXTURES / "evil_morty_lyrics.txt").read_text()
USER_LEVEL = "A1"  # matches the level used when the source was originally analyzed


CEFR_DATA_DIR = Path(__file__).resolve().parents[3] / "dictionaries" / "cefr"
CAMBRIDGE_PATH = Path(__file__).resolve().parents[3] / "dictionaries" / "cambridge.jsonl"


def _make_classifier() -> VotingCEFRClassifier:
    cambridge_data = parse_cambridge_jsonl(CAMBRIDGE_PATH)
    cambridge_cefr = CambridgeCEFRSource.from_data(cambridge_data)
    sources = [
        CefrpyCEFRSource(),
        EFLLexCEFRSource(CEFR_DATA_DIR / "efllex.tsv"),
        OxfordCEFRSource(CEFR_DATA_DIR / "oxford5000.csv"),
        KellyCEFRSource(CEFR_DATA_DIR / "kelly.csv"),
    ]
    return VotingCEFRClassifier(sources, priority_source=cambridge_cefr)


@pytest.fixture(scope="module")
def use_case() -> AnalyzeTextUseCase:
    return AnalyzeTextUseCase(
        text_cleaner=RegexTextCleaner(),
        text_analyzer=SpaCyTextAnalyzer(),
        cefr_classifier=_make_classifier(),
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
    ("45_look_at", "look at", "two of them stopped and looked at Harry"),
    (
        "86_disclaimer",
        "disclaimer",
        "Disclaimer: J. K. Rowling owns Harry Potter, "
        "and no one owns the methods of rationality.",
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
        "science is that the final arbiter is observation",
    ),
    (
        "305_plot",
        "plot",
        "whose episodes are individually plotted",
    ),
    (
        "318_argument",
        "argument",
        "know I can't win arguments with you",
    ),
    (
        "348_require",
        "require",
        "any chapter, no login required, and there's",
    ),
    (
        "354_correct",
        "correct",
        "The story has been corrected to British English",
    ),
    (
        "456_single",
        "single",
        "This is not a strict single-point",
    ),
    (
        "474_own",
        "own",
        "Disclaimer: J. K. Rowling owns Harry Potter",
    ),
    (
        "289_fic",
        "fic",
        "This fic is widely considered",
    ),
    (
        "394_consider",
        "consider",
        "This fic is widely considered to have really hit",
    ),
]

WAVE_1_LYRICS: list[tuple[str, str, str]] = [
    ("485_answer_to", "answer to", "I answer to nobody, Rick"),
    ("509_dimension", "dimension", "ending Ricks of all dimensions"),
    ("521_genius", "genius", "forming me\nInto a genius"),
    (
        "486_believe_in",
        "believe in",
        "believe in this Citadel to the Ricks and Mortys",
    ),
    ("525_defame", "defame", "Defamed by the fake news"),
    ("552_leave", "leave", "left for a Morty without"),
    (
        "554_cause",
        "cause",
        "Cause he never heard me say\n\u201cah geez",
    ),
]


# Wave 2 wishlist — these still produce the *original* (unfixed) fragment.
# Each entry is (test_id, lemma, current_buggy_fragment, reason).
WAVE_2_HPMOR_XFAIL: list[tuple[str, str, str, str]] = [
    (
        "235_conclusion",
        "conclusion",
        "arc building to a final conclusion.",
        "needs LEFT extension 'with an overall'",
    ),
    (
        "477_need",
        "need",
        "no need to finish reading it all",
        "needs LEFT extension 'there's'",
    ),
]

WAVE_2_LYRICS_XFAIL: list[tuple[str, str, str, str]] = []


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


@pytest.mark.integration
class TestWave2WishlistHPMOR:
    """Wave 2 should fix these. xfail(strict=True) → if a future wave makes
    them pass, the test will FAIL with 'unexpectedly passing' and force
    updating the fixture."""

    @pytest.mark.parametrize(
        ("lemma", "current_buggy"),
        [(lemma, buggy) for _, lemma, buggy, _ in WAVE_2_HPMOR_XFAIL],
        ids=[tid for tid, _, _, _ in WAVE_2_HPMOR_XFAIL],
    )
    @pytest.mark.xfail(strict=True, reason="Wave 2 — needs extension, not trim")
    def test_fragment_should_be_fixed(
        self, hpmor_fragments: dict[str, str], lemma: str, current_buggy: str
    ) -> None:
        actual = hpmor_fragments.get(lemma)
        # The xfail expectation: today the value still equals the buggy one,
        # so we ASSERT IT'S DIFFERENT. When a wave fixes it, this assert
        # passes and the xfail strict mode flips to FAIL.
        assert actual != current_buggy


@pytest.mark.integration
class TestWave2WishlistLyrics:
    @pytest.mark.parametrize(
        ("lemma", "current_buggy"),
        [(lemma, buggy) for _, lemma, buggy, _ in WAVE_2_LYRICS_XFAIL],
        ids=[tid for tid, _, _, _ in WAVE_2_LYRICS_XFAIL],
    )
    @pytest.mark.xfail(strict=True, reason="Wave 2 / Wave 3 — lyrics line break")
    def test_fragment_should_be_fixed(
        self, lyrics_fragments: dict[str, str], lemma: str, current_buggy: str
    ) -> None:
        actual = lyrics_fragments.get(lemma)
        assert actual != current_buggy
