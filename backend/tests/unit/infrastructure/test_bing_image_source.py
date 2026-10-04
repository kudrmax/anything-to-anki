"""BingImageSource reads thumbnails out of Bing's image results page."""
from __future__ import annotations

import html
import json

import pytest
from backend.domain.exceptions import ImageSearchError
from backend.domain.value_objects.image_provider import ImageProvider
from backend.infrastructure.adapters.bing_image_source import BingImageSource

pytestmark = pytest.mark.unit


def _tile(thumbnail: str) -> str:
    metadata = html.escape(json.dumps({"turl": thumbnail, "murl": "https://shop.example/big.jpg"}))
    return f'<a class="iusc" m="{metadata}" href="#">tile</a>'


def _page(*thumbnails: str) -> bytes:
    return ("<div>" + "".join(_tile(t) for t in thumbnails) + "</div>").encode()


class TestBingImageSource:
    def test_returns_bing_thumbnails_in_result_order(self) -> None:
        page = _page("https://ts1.mm.bing.net/th?id=A", "https://ts2.mm.bing.net/th?id=B")

        images = BingImageSource(fetch=lambda _url: page).find_images("ladder")

        assert [image.url for image in images] == [
            "https://ts1.mm.bing.net/th?id=A", "https://ts2.mm.bing.net/th?id=B",
        ]
        assert {image.provider for image in images} == {ImageProvider.BING}

    def test_searches_for_the_word(self) -> None:
        asked: list[str] = []

        def fetch(url: str) -> bytes:
            asked.append(url)
            return _page()

        BingImageSource(fetch=fetch).find_images("rain gutter")

        assert "q=rain+gutter" in asked[0]

    def test_skips_duplicates_foreign_hosts_and_broken_tiles(self) -> None:
        page = _page(
            "https://ts1.mm.bing.net/th?id=A",
            "https://ts1.mm.bing.net/th?id=A",
            "https://cdn.example/x.jpg",
        ) + b'<a m="{not json}">broken</a>'

        images = BingImageSource(fetch=lambda _url: page).find_images("ladder")

        assert [image.url for image in images] == ["https://ts1.mm.bing.net/th?id=A"]

    def test_caps_the_number_of_results(self) -> None:
        page = _page(*(f"https://ts1.mm.bing.net/th?id={i}" for i in range(5)))

        images = BingImageSource(max_results=2, fetch=lambda _url: page).find_images("ladder")

        assert len(images) == 2

    def test_network_failure_is_a_search_error(self) -> None:
        def broken(_url: str) -> bytes:
            raise OSError("timed out")

        with pytest.raises(ImageSearchError):
            BingImageSource(fetch=broken).find_images("ladder")

    @pytest.mark.parametrize(("url", "owned"), [
        ("https://ts2.mm.bing.net/th?id=A", True),
        ("http://ts2.mm.bing.net/th?id=A", False),
        ("https://mm.bing.net.evil.example/th", False),
    ])
    def test_owns_only_bing_thumbnail_urls(self, url: str, owned: bool) -> None:
        assert BingImageSource(fetch=lambda _url: b"").owns(url) is owned
