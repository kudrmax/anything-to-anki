from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.search_target_images import SearchTargetImagesUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    CandidateNotFoundError,
    ImageSearchError,
)
from backend.domain.ports.target_image_source import TargetImageSource
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.image_option import ImageOption
from backend.domain.value_objects.image_provider import ImageProvider

pytestmark = pytest.mark.unit

CANDIDATE_ID = 7


def _candidate(pos: str = "NOUN") -> StoredCandidate:
    return StoredCandidate(
        id=CANDIDATE_ID, source_id=1, lemma="ladder", pos=pos, cefr_level="B1",
        zipf_frequency=3.5, context_fragment="climb the ladder", fragment_purity="clean",
        occurrences=1, status=CandidateStatus.PENDING,
    )


def _source(*urls: str, provider: ImageProvider = ImageProvider.BING) -> MagicMock:
    source = MagicMock(spec=TargetImageSource)
    source.find_images.return_value = [ImageOption(url=url, provider=provider) for url in urls]
    return source


def _failing_source() -> MagicMock:
    source = MagicMock(spec=TargetImageSource)
    source.find_images.side_effect = ImageSearchError("down")
    return source


def _use_case(
    *sources: MagicMock, candidate: StoredCandidate | None = None,
) -> SearchTargetImagesUseCase:
    repo = MagicMock()
    repo.get_by_id.return_value = candidate if candidate is not None else _candidate()
    return SearchTargetImagesUseCase(candidate_repo=repo, image_sources=list(sources))


class TestSearchTargetImages:
    def test_lists_pictures_of_all_sources_in_source_order(self) -> None:
        wiktionary = _source("https://w/1", provider=ImageProvider.WIKTIONARY)
        bing = _source("https://b/1", "https://b/2")

        result = _use_case(wiktionary, bing).execute(CANDIDATE_ID)

        assert [(o.url, o.provider) for o in result.options] == [
            ("https://w/1", "wiktionary"), ("https://b/1", "bing"), ("https://b/2", "bing"),
        ]
        wiktionary.find_images.assert_called_once_with("ladder")

    def test_reports_the_target_as_the_query_by_default(self) -> None:
        assert _use_case(_source()).execute(CANDIDATE_ID).query == "ladder"

    def test_searches_by_a_free_text_query_instead_of_the_target(self) -> None:
        source = _source("https://b/1")

        result = _use_case(source).execute(CANDIDATE_ID, query="  rope ladder  ")

        source.find_images.assert_called_once_with("rope ladder")
        assert result.query == "rope ladder"

    @pytest.mark.parametrize("query", ["", "   "])
    def test_a_blank_query_falls_back_to_the_target(self, query: str) -> None:
        source = _source()

        _use_case(source).execute(CANDIDATE_ID, query=query)

        source.find_images.assert_called_once_with("ladder")

    def test_drops_a_picture_offered_twice(self) -> None:
        result = _use_case(_source("https://x/1"), _source("https://x/1")).execute(CANDIDATE_ID)

        assert [o.url for o in result.options] == ["https://x/1"]

    def test_a_failing_source_does_not_hide_the_others(self) -> None:
        result = _use_case(_failing_source(), _source("https://b/1")).execute(CANDIDATE_ID)

        assert [o.url for o in result.options] == ["https://b/1"]

    def test_fails_when_no_source_answers(self) -> None:
        with pytest.raises(ImageSearchError):
            _use_case(_failing_source(), _failing_source()).execute(CANDIDATE_ID)

    def test_nothing_found_is_an_empty_list_not_an_error(self) -> None:
        assert _use_case(_source()).execute(CANDIDATE_ID).options == []

    @pytest.mark.parametrize("pos", ["VERB", "ADJ", "ADV"])
    def test_searches_for_any_part_of_speech(self, pos: str) -> None:
        source = _source("https://b/1")

        result = _use_case(source, candidate=_candidate(pos=pos)).execute(CANDIDATE_ID)

        assert [o.url for o in result.options] == ["https://b/1"]

    def test_unknown_candidate(self) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = None
        use_case = SearchTargetImagesUseCase(candidate_repo=repo, image_sources=[])

        with pytest.raises(CandidateNotFoundError):
            use_case.execute(CANDIDATE_ID)
