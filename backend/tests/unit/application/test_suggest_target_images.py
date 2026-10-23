"""Suggested pictures: the search runs in the background, the answer comes at once."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.suggest_target_images import SuggestTargetImagesUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.ports.background_picture_searches import BackgroundPictureSearches
from backend.domain.ports.target_image_source import TargetImageSource
from backend.domain.value_objects.image_option import ImageOption
from backend.domain.value_objects.image_provider import ImageProvider
from backend.domain.value_objects.picture_search import PictureSearch, PictureSearchStatus
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

pytestmark = pytest.mark.unit

PICTURE = ImageOption(url="https://pictures/ladder.jpg", provider=ImageProvider.WIKTIONARY)


class _Searches(BackgroundPictureSearches):
    """Runs nothing until told: what a request sees while the search is going."""

    def __init__(self, state: PictureSearch) -> None:
        self.state = state
        self.asked: list[str] = []
        self.finds: list[Callable[[], Sequence[ImageOption]]] = []

    def search(self, key: str, find: Callable[[], Sequence[ImageOption]]) -> PictureSearch:
        self.asked.append(key)
        self.finds.append(find)
        return self.state


def _use_case(
    searches: _Searches, candidate: StoredCandidate | None = None,
) -> SuggestTargetImagesUseCase:
    repo = MagicMock()
    repo.get_by_id.return_value = candidate
    settings = MagicMock()
    settings.get.return_value = None
    source = MagicMock(spec=TargetImageSource)
    source.find_images.return_value = [PICTURE]
    return SuggestTargetImagesUseCase(
        candidate_repo=repo, settings_repo=settings, image_sources=[source], searches=searches,
    )


def _ladder() -> StoredCandidate:
    return StoredCandidate(
        id=7, source_id=1, lemma="Ladder", pos="NOUN", cefr_level="B1", zipf_frequency=3.5,
        occurrences=1, status=WordStatus.NEW,
    )


def test_while_the_search_runs_the_answer_says_searching_with_no_pictures() -> None:
    searches = _Searches(PictureSearch(PictureSearchStatus.SEARCHING))
    answer = _use_case(searches, _ladder()).execute(7)
    assert (answer.status, answer.query, answer.options) == ("searching", "Ladder", [])


def test_a_finished_search_gives_its_pictures_and_runs_the_finder_for_the_lemma() -> None:
    searches = _Searches(PictureSearch(PictureSearchStatus.READY, (PICTURE,)))
    answer = _use_case(searches, _ladder()).execute(7)
    assert answer.status == "ready"
    assert [o.url for o in answer.options] == [PICTURE.url]
    assert searches.asked[0].startswith("ladder:")
    assert list(searches.finds[0]()) == [PICTURE]


def test_an_unknown_word_is_not_found() -> None:
    with pytest.raises(CandidateNotFoundError):
        _use_case(_Searches(PictureSearch(PictureSearchStatus.SEARCHING))).execute(7)
