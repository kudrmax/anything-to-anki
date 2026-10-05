"""YandexImageSource reads thumbnails out of the state embedded in Yandex's results page."""
from __future__ import annotations

import html
import json

import pytest
from backend.domain.exceptions import ImageSearchError
from backend.domain.value_objects.image_provider import ImageProvider
from backend.infrastructure.adapters.yandex_image_source import YandexImageSource

pytestmark = pytest.mark.unit

LIMIT = 12


def _page(*thumb_ids: str) -> bytes:
    """Mimics the page: result state as HTML-escaped JSON, each thumbnail listed twice."""
    results = [
        {
            "image": f"//avatars.mds.yandex.net/i?id={tid}&n=13",
            "thumb": {"url": f"//avatars.mds.yandex.net/i?id={tid}&n=13", "w": 480, "h": 320},
        }
        for tid in thumb_ids
    ]
    state = html.escape(json.dumps({"results": results}, separators=(",", ":")))
    return f'<div data-state="{state}"></div>'.encode()


class TestYandexImageSource:
    def test_returns_thumbnails_in_result_order_once_each(self) -> None:
        page = _page("aaa-images-thumbs", "bbb-images-thumbs")

        images = YandexImageSource(fetch=lambda _url: page).find_images("ladder", LIMIT)

        assert [image.url for image in images] == [
            "https://avatars.mds.yandex.net/i?id=aaa-images-thumbs&n=13",
            "https://avatars.mds.yandex.net/i?id=bbb-images-thumbs&n=13",
        ]
        assert {image.provider for image in images} == {ImageProvider.YANDEX}

    def test_searches_for_the_word(self) -> None:
        asked: list[str] = []

        def fetch(url: str) -> bytes:
            asked.append(url)
            return _page()

        YandexImageSource(fetch=fetch).find_images("give in", LIMIT)

        assert "text=give+in" in asked[0]

    def test_returns_at_most_the_limit(self) -> None:
        page = _page(*(f"id{i}" for i in range(5)))

        assert len(YandexImageSource(fetch=lambda _url: page).find_images("ladder", 2)) == 2

    def test_nothing_found_is_an_empty_list(self) -> None:
        assert YandexImageSource(fetch=lambda _url: _page()).find_images("qwzx", LIMIT) == []

    def test_captcha_is_a_search_error(self) -> None:
        page = b'<form action="/checkcaptcha"><img class="captcha__image"></form>'

        with pytest.raises(ImageSearchError):
            YandexImageSource(fetch=lambda _url: page).find_images("ladder", LIMIT)

    def test_network_failure_is_a_search_error(self) -> None:
        def broken(_url: str) -> bytes:
            raise OSError("timed out")

        with pytest.raises(ImageSearchError):
            YandexImageSource(fetch=broken).find_images("ladder", LIMIT)

    @pytest.mark.parametrize(("url", "owned"), [
        ("https://avatars.mds.yandex.net/i?id=a&n=13", True),
        ("http://avatars.mds.yandex.net/i?id=a&n=13", False),
        ("https://avatars.mds.yandex.net.evil.example/i", False),
    ])
    def test_owns_only_yandex_thumbnail_urls(self, url: str, owned: bool) -> None:
        assert YandexImageSource(fetch=lambda _url: b"").owns(url) is owned
