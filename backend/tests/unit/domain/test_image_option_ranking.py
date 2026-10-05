from __future__ import annotations

import pytest
from backend.domain.services.image_option_ranking import rank_image_options
from backend.domain.value_objects.image_option import ImageOption
from backend.domain.value_objects.image_provider import ImageProvider

pytestmark = pytest.mark.unit


def _options(provider: ImageProvider, *names: str) -> list[ImageOption]:
    return [ImageOption(url=f"https://{name}", provider=provider) for name in names]


def _urls(options: list[ImageOption]) -> list[str]:
    return [option.url.removeprefix("https://") for option in options]


class TestRankImageOptions:
    def test_dictionary_first_then_search_engines_in_turns(self) -> None:
        ranked = rank_image_options([
            _options(ImageProvider.WIKTIONARY, "w1", "w2"),
            _options(ImageProvider.BING, "b1", "b2", "b3"),
            _options(ImageProvider.YANDEX, "y1", "y2"),
        ])

        assert _urls(ranked) == ["w1", "w2", "b1", "y1", "b2", "y2", "b3"]

    def test_dictionary_goes_first_whatever_the_source_order(self) -> None:
        ranked = rank_image_options([
            _options(ImageProvider.BING, "b1"),
            _options(ImageProvider.WIKTIONARY, "w1"),
        ])

        assert _urls(ranked) == ["w1", "b1"]

    def test_one_engine_left_keeps_its_order(self) -> None:
        ranked = rank_image_options([
            _options(ImageProvider.BING),
            _options(ImageProvider.YANDEX, "y1", "y2"),
        ])

        assert _urls(ranked) == ["y1", "y2"]

    def test_a_picture_offered_twice_stays_where_it_first_appears(self) -> None:
        ranked = rank_image_options([
            _options(ImageProvider.BING, "same", "b2"),
            _options(ImageProvider.YANDEX, "same", "y2"),
        ])

        assert _urls(ranked) == ["same", "b2", "y2"]

    def test_nothing_found(self) -> None:
        assert rank_image_options([]) == []
