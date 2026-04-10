"""End-to-end test of the fragment selection pipeline against the 20 real
'bad fragment' cases collected by the user from HPMOR (source 1) and
'Evil Morty' lyrics (source 2).

For each case we:
1. Run real spaCy on the full sentence containing the target.
2. Find the target token by surface form (and an occurrence index when needed).
3. Call ``FragmentSelector.select`` to obtain the cleaned fragment indices.
4. Render text from those indices.

The test asserts the cleaned text matches a hand-written 'expected' value.
Where Wave 1 (pure trim) cannot reach the expected value (because extension
is needed), the case is marked xfail with a reason — those will be the
target of Wave 2 (clause segmentation + generate-and-rank).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.services.fragment_selection import FragmentSelector
from backend.domain.services.fragment_selection.rendering import render_fragment
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.entities.token_data import TokenData


def _zero_unknown_counter(
    _indices: Sequence[int], _tokens: list[TokenData]
) -> int:
    return 0

# Sentences from HPMOR (source 1).
S_DISCLAIMER = (
    "Disclaimer: J. K. Rowling owns Harry Potter, "
    "and no one owns the methods of rationality."
)
S_FIC = (
    "This fic is widely considered to have really hit its stride "
    "starting at around Chapter 5."
)
S_REVIEWS = (
    "You can leave reviews on any chapter, no login required, "
    "and there's no need to finish reading it all before you start "
    "reviewing chapters - but do please leave at most one review per chapter."
)
S_SINGLE_POINT = (
    "This is not a strict single-point-of-departure fic - there exists a "
    "primary point of departure, at some point in the past, but also "
    "other alterations."
)
S_PACING = (
    "The pacing of the story is that of serial fiction, i.e., that of a TV "
    "show running for a predetermined number of seasons, whose episodes are "
    "individually plotted but with an overall arc building to a final conclusion."
)
S_BRITPICK = (
    "The story has been corrected to British English up to Ch. 17, "
    "and further Britpicking is currently in progress (see the /HPMOR subreddit)."
)
S_ARBITER = (
    "There's a quote there about how philosophers say a great deal about "
    "what science absolutely requires, and it is all wrong, because the only "
    "rule in science is that the final arbiter is observation - that you "
    "just have to look at the world and report what you see."
)
S_ARGUMENT = (
    "My love, I know I can't win arguments with you, "
    "but please, you have to trust me on this -"
)
S_LOOKED_AT = (
    "The two of them stopped and looked at Harry as though they'd "
    "forgotten there was a third person in the room."
)

# Sentences from 'Evil Morty' lyrics (source 2).
S_ANSWER_TO = "I answer to nobody, Rick or authority"
S_BELIEVE_IN = (
    "A message from the Ricks and Mortys that believe in this Citadel "
    "to the Ricks and Mortys that don't: You're outnumbered!"
)
S_DEFAME = "Defamed by the fake news as a joke"
S_LEAVE = "And left for a Morty without any brains"
# Lyrics with line breaks — spaCy can sentencize on these or not.
S_DIMENSION = (
    "Did I mention ending Ricks of all dimensions then I get\n"
    "Their Mortys torture them from night to morning"
)
S_GENIUS = (
    "When I was born that prick had tried forming me\nInto a genius. "
    "I wanted more to see."
)


@pytest.mark.integration
class TestBoundaryCleanerRealCases:
    @classmethod
    def setup_class(cls) -> None:
        cls.analyzer = SpaCyTextAnalyzer()
        cls.selector = FragmentSelector()

    def _run(
        self,
        sentence: str,
        target_text: str,
        target_occurrence: int = 0,
        protected_extra: tuple[str, ...] = (),
    ) -> tuple[str, str]:
        """Return (raw_fragment_before_cleanup, cleaned_fragment).

        target_text — case-insensitive surface form to locate target token.
        target_occurrence — pick the n-th occurrence (0-based) when text repeats.
        protected_extra — extra surface forms to also protect (for phrasal verbs).
        """
        tokens = self.analyzer.analyze(sentence)

        # Find target token by surface form.
        target_idx: int | None = None
        seen = 0
        for t in tokens:
            if (
                t.text.lower() == target_text.lower()
                or t.lemma.lower() == target_text.lower()
            ):
                if seen == target_occurrence:
                    target_idx = t.index
                    break
                seen += 1
        assert target_idx is not None, (
            f"target {target_text!r} (occurrence {target_occurrence}) "
            f"not found in: {sentence}"
        )

        # Build protected set: target + any extras (phrasal verb particles).
        protected: set[int] = {target_idx}
        for extra in protected_extra:
            for t in tokens:
                if t.text.lower() == extra.lower():
                    protected.add(t.index)
                    break

        # Pipeline: FragmentSelector does generate → clean → score → pick.
        cleaned_indices = self.selector.select(
            tokens=tokens,
            target_index=target_idx,
            protected_indices=frozenset(protected),
            unknown_counter=_zero_unknown_counter,
        )
        cleaned_text = render_fragment(tokens, cleaned_indices)
        # "raw_text" had historical meaning of pre-cleanup fragment; with
        # the new pipeline the raw phase is internal. Return the cleaned
        # text as raw too so the signature is preserved.
        return cleaned_text, cleaned_text

    # ---------------------------------------------------------- HPMOR cases

    def test_45_look_at_phrasal(self) -> None:
        # WAVE 1 GOAL: drop "as though they" right edge.
        # Wave 1 result: "two of them stopped and looked at Harry"
        # Final goal:    "The two of them stopped and looked at Harry" (needs left extend)
        raw, cleaned = self._run(
            S_LOOKED_AT, "looked", protected_extra=("at",)
        )
        # Wave 1 expected: at minimum, no dangling "they" / "as though"
        assert not cleaned.endswith("they")
        assert "as though" not in cleaned
        assert "looked at Harry" in cleaned

    def test_86_disclaimer(self) -> None:
        _, cleaned = self._run(S_DISCLAIMER, "disclaimer")
        assert "Harry Potter" in cleaned

    def test_138_individually(self) -> None:
        _, cleaned = self._run(S_PACING, "individually")
        assert not cleaned.endswith("but")
        assert "individually plotted" in cleaned

    def test_201_serial(self) -> None:
        _, cleaned = self._run(S_PACING, "serial")
        assert not cleaned.rstrip(".").endswith("that")
        assert "serial fiction" in cleaned

    @pytest.mark.xfail(
        reason="Wave 2: needs LEFT extension to grab 'an overall'",
        strict=False,
    )
    def test_235_conclusion(self) -> None:
        _, cleaned = self._run(S_PACING, "conclusion")
        assert "overall arc" in cleaned

    def test_288_arbiter(self) -> None:
        _, cleaned = self._run(S_ARBITER, "arbiter")
        # Wave 1 goal: at minimum, no dangling "that you" right.
        assert not cleaned.endswith("that you")
        assert "arbiter is observation" in cleaned

    @pytest.mark.xfail(
        reason="Wave 2: needs RIGHT extension to complete VP 'really hit its stride'",
        strict=False,
    )
    def test_289_fic(self) -> None:
        _, cleaned = self._run(S_FIC, "fic")
        assert "stride" in cleaned

    def test_305_plot_verb(self) -> None:
        _, cleaned = self._run(S_PACING, "plotted")
        assert not cleaned.endswith("but")
        assert "plotted" in cleaned

    def test_318_argument(self) -> None:
        _, cleaned = self._run(S_ARGUMENT, "arguments")
        # Wave 1 goal: drop "but please" right.
        assert "but please" not in cleaned
        assert "win arguments" in cleaned

    @pytest.mark.xfail(
        reason="Wave 2: cascade trim is risky here, leaves an awkward edge",
        strict=False,
    )
    def test_348_require(self) -> None:
        _, cleaned = self._run(S_REVIEWS, "required")
        assert "no login required" in cleaned
        assert "and there" not in cleaned

    def test_354_correct_verb(self) -> None:
        _, cleaned = self._run(S_BRITPICK, "corrected")
        assert not cleaned.endswith("up to")
        assert not cleaned.endswith("up")
        assert "British English" in cleaned

    @pytest.mark.xfail(
        reason="Wave 2: needs RIGHT extension to grab 'stride'",
        strict=False,
    )
    def test_394_consider_verb(self) -> None:
        _, cleaned = self._run(S_FIC, "considered")
        assert "stride" in cleaned

    def test_474_own_verb(self) -> None:
        _, cleaned = self._run(S_DISCLAIMER, "owns")
        # Wave 1 goal: drop ", and no" right.
        assert not cleaned.rstrip(".").endswith("no")
        assert "owns Harry Potter" in cleaned

    @pytest.mark.xfail(
        reason="Wave 2: needs LEFT extension to grab expletive 'there's'",
        strict=False,
    )
    def test_477_need_noun(self) -> None:
        _, cleaned = self._run(S_REVIEWS, "need")
        assert "there's no need" in cleaned or "there is no need" in cleaned

    # ---------------------------------------------------------- LYRICS cases

    def test_485_answer_to_phrasal(self) -> None:
        _, cleaned = self._run(
            S_ANSWER_TO, "answer", protected_extra=("to",)
        )
        # Whole line fits in MAX (≤ 12 content words) → Step 0 should already
        # return it whole. So even raw should be clean.
        assert "answer to nobody" in cleaned
        assert not cleaned.endswith("or")

    def test_486_believe_in_phrasal(self) -> None:
        _, cleaned = self._run(
            S_BELIEVE_IN, "believe", protected_extra=("in",)
        )
        # Wave 1 goal: drop relativizer "that" from left.
        assert not cleaned.startswith("that ")
        assert "believe in this Citadel" in cleaned

    @pytest.mark.xfail(
        reason="Wave 2/3: lyrics line break + needs LEFT extension 'Did I'",
        strict=False,
    )
    def test_509_dimension(self) -> None:
        _, cleaned = self._run(S_DIMENSION, "dimensions")
        assert "Did I mention" in cleaned
        assert "Their" not in cleaned

    def test_521_genius(self) -> None:
        _, cleaned = self._run(S_GENIUS, "genius")
        # Either expansion is acceptable; "Into a genius" must be present and
        # the fragment should make sense.
        assert "genius" in cleaned

    def test_525_defame_verb(self) -> None:
        _, cleaned = self._run(S_DEFAME, "Defamed")
        # Whole line is short (≤ MAX) so Step 0 returns it whole.
        # If it ends in dangling "as", we strip; ideal Wave 1 ends "fake news".
        assert not cleaned.endswith("as")

    def test_552_leave_verb(self) -> None:
        _, cleaned = self._run(S_LEAVE, "left")
        # Wave 1 goal: drop "And" left and "any" right.
        assert not cleaned.startswith("And ")
        assert not cleaned.endswith("any")
