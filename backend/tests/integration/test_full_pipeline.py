import pytest
from backend.application.dto.analysis_dtos import AnalyzeTextRequest
from backend.infrastructure.container import Container


@pytest.mark.integration
class TestFullPipeline:
    def setup_method(self) -> None:
        self.container = Container()
        self.use_case = self.container.analyze_text_use_case()

    def test_basic_text(self) -> None:
        request = AnalyzeTextRequest(
            raw_text="The relentless pursuit of perfection often leads to burnout.",
            user_level="B1",
        )
        response = self.use_case.execute(request)

        assert response.total_tokens > 0
        assert len(response.candidates) > 0

        lemmas = {c.lemma for c in response.candidates}
        # These words should be above B1
        assert "relentless" in lemmas or "pursuit" in lemmas or "burnout" in lemmas

    def test_all_simple_words(self) -> None:
        request = AnalyzeTextRequest(
            raw_text="I have a big red cat.",
            user_level="B1",
        )
        response = self.use_case.execute(request)
        # All A1/A2 words — should have few or no candidates
        assert len(response.candidates) <= 1

    def test_with_timecodes(self) -> None:
        request = AnalyzeTextRequest(
            raw_text="[00:01:23] The relentless pursuit [Music] of perfection.",
            user_level="B1",
        )
        response = self.use_case.execute(request)

        assert "[00:01:23]" not in response.cleaned_text
        assert "[Music]" not in response.cleaned_text
        assert len(response.candidates) > 0

    def test_candidates_have_fragments(self) -> None:
        request = AnalyzeTextRequest(
            raw_text="The relentless pursuit of perfection often leads to burnout.",
            user_level="B1",
        )
        response = self.use_case.execute(request)

        for candidate in response.candidates:
            assert candidate.context_fragment != ""
            assert candidate.fragment_purity in ("clean", "dirty")

    def test_candidates_have_sweet_spot_info(self) -> None:
        request = AnalyzeTextRequest(
            raw_text="The relentless pursuit of perfection often leads to burnout.",
            user_level="B1",
        )
        response = self.use_case.execute(request)

        for candidate in response.candidates:
            assert isinstance(candidate.is_sweet_spot, bool)
            assert candidate.zipf_frequency >= 0
