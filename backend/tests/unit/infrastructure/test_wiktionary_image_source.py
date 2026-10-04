"""WiktionaryImageSource takes pictures only from the English entry of a word."""
from __future__ import annotations

import json
import urllib.parse

import pytest
from backend.domain.exceptions import ImageSearchError
from backend.domain.value_objects.image_provider import ImageProvider
from backend.infrastructure.adapters.wiktionary_image_source import WiktionaryImageSource

pytestmark = pytest.mark.unit

LADDER_WIKITEXT = """==English==
[[File:Step ladder.jpg|thumb|A step ladder]]
===Noun===
# A frame of rungs.
[[Image:Stocking_run.jpg|thumb|A ladder in tights]]
[[File:LL-Q1860 (eng)-ladder.wav]]
<gallery>
File:Rope ladder.png|A rope ladder
</gallery>

==Dutch==
[[File:Ladder (Dutch).jpg|thumb]]
"""

THUMBS = {
    "File:Step ladder.jpg": "https://thumb.wikimedia.org/step.jpg",
    "File:Stocking run.jpg": "https://thumb.wikimedia.org/run.jpg",
    "File:Rope ladder.png": "https://thumb.wikimedia.org/rope.png",
}


class _FakeWiki:
    """Answers the two MediaWiki queries the source makes."""

    def __init__(self, wikitext: str | None) -> None:
        self._wikitext = wikitext
        self.asked_files: list[str] = []

    def __call__(self, url: str) -> bytes:
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        if url.startswith("https://en.wiktionary.org/"):
            return self._entry(params["titles"])
        self.asked_files = params["titles"].split("|")
        return self._thumbnails(self.asked_files)

    def _entry(self, title: str) -> bytes:
        if self._wikitext is None:
            return json.dumps({"query": {"pages": [{"title": title, "missing": True}]}}).encode()
        page = {"title": title, "revisions": [{"slots": {"main": {"content": self._wikitext}}}]}
        return json.dumps({"query": {"pages": [page]}}).encode()

    @staticmethod
    def _thumbnails(titles: list[str]) -> bytes:
        normalized = [{"from": t, "to": t.replace("_", " ")} for t in titles if "_" in t]
        pages = [
            {"title": title, "imageinfo": [{"thumburl": THUMBS[title]}]}
            for title in (t.replace("_", " ") for t in titles)
            if title in THUMBS
        ]
        return json.dumps({"query": {"normalized": normalized, "pages": pages}}).encode()


class TestWiktionaryImageSource:
    def test_returns_pictures_of_the_english_entry_in_page_order(self) -> None:
        source = WiktionaryImageSource(fetch=_FakeWiki(LADDER_WIKITEXT))

        images = source.find_images("ladder")

        assert [image.url for image in images] == [
            "https://thumb.wikimedia.org/step.jpg",
            "https://thumb.wikimedia.org/run.jpg",
            "https://thumb.wikimedia.org/rope.png",
        ]
        assert {image.provider for image in images} == {ImageProvider.WIKTIONARY}

    def test_ignores_other_languages_and_non_pictures(self) -> None:
        wiki = _FakeWiki(LADDER_WIKITEXT)

        WiktionaryImageSource(fetch=wiki).find_images("ladder")

        assert "File:Ladder (Dutch).jpg" not in wiki.asked_files
        assert not any(name.endswith(".wav") for name in wiki.asked_files)

    def test_entry_without_pictures(self) -> None:
        source = WiktionaryImageSource(fetch=_FakeWiki("==English==\n===Noun===\n# A word.\n"))

        assert source.find_images("procrastination") == []

    def test_missing_entry(self) -> None:
        assert WiktionaryImageSource(fetch=_FakeWiki(None)).find_images("qwzx") == []

    def test_word_with_only_a_foreign_entry(self) -> None:
        source = WiktionaryImageSource(fetch=_FakeWiki("==Dutch==\n[[File:Huis.jpg]]\n"))

        assert source.find_images("huis") == []

    def test_network_failure_is_a_search_error(self) -> None:
        def broken(_url: str) -> bytes:
            raise OSError("no route to host")

        with pytest.raises(ImageSearchError):
            WiktionaryImageSource(fetch=broken).find_images("ladder")

    def test_garbage_answer_is_a_search_error(self) -> None:
        with pytest.raises(ImageSearchError):
            WiktionaryImageSource(fetch=lambda _url: b"<html>").find_images("ladder")

    @pytest.mark.parametrize(("url", "owned"), [
        ("https://thumb.wikimedia.org/wikipedia/commons/thumb/a/b.jpg", True),
        ("https://upload.wikimedia.org/wikipedia/commons/a/b.jpg", True),
        ("http://upload.wikimedia.org/wikipedia/commons/a/b.jpg", False),
        ("https://upload.wikimedia.org.evil.example/b.jpg", False),
    ])
    def test_owns_only_wikimedia_https_urls(self, url: str, owned: bool) -> None:
        assert WiktionaryImageSource(fetch=_FakeWiki(None)).owns(url) is owned
