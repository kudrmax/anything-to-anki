"""Builds small epub files for tests."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

CONTAINER_XML = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""


def prose(words: int, seed: str = "word") -> str:
    """A paragraph of exactly `words` words."""
    return " ".join(f"{seed}{'a' * (i % 5)}" for i in range(words))


def page(body: str, body_attrs: str = "") -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
        f"<head><title>t</title></head><body {body_attrs}>{body}</body></html>"
    )


@dataclass
class TocLink:
    label: str
    href: str
    children: list[TocLink] = field(default_factory=list)


@dataclass
class EpubBuilder:
    title: str = "A Book"
    documents: list[tuple[str, str]] = field(default_factory=list)
    nav: list[TocLink] | None = None
    ncx: list[TocLink] | None = None
    with_container: bool = True
    with_opf: bool = True

    def add(self, name: str, markup: str) -> EpubBuilder:
        self.documents.append((name, markup))
        return self

    def write(self, path: Path) -> Path:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            if self.with_container:
                archive.writestr("META-INF/container.xml", CONTAINER_XML)
            if self.with_opf:
                archive.writestr("OEBPS/content.opf", self._opf())
            for name, markup in self.documents:
                archive.writestr(f"OEBPS/{name}", markup)
            if self.nav is not None:
                archive.writestr("OEBPS/nav.xhtml", self._nav())
            if self.ncx is not None:
                archive.writestr("OEBPS/toc.ncx", self._ncx())
        return path

    def _opf(self) -> str:
        items = "".join(
            f'<item id="d{i}" href="{name}" media-type="application/xhtml+xml"/>'
            for i, (name, _) in enumerate(self.documents)
        )
        if self.nav is not None:
            items += (
                '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"'
                ' properties="nav"/>'
            )
        if self.ncx is not None:
            items += '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
        refs = "".join(f'<itemref idref="d{i}"/>' for i in range(len(self.documents)))
        toc_attr = ' toc="ncx"' if self.ncx is not None else ""
        return (
            '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{self.title}</dc:title></metadata>'
            f"<manifest>{items}</manifest><spine{toc_attr}>{refs}</spine></package>"
        )

    def _nav(self) -> str:
        def render(links: list[TocLink]) -> str:
            inner = "".join(
                f'<li><a href="{link.href}">{link.label}</a>'
                + (render(link.children) if link.children else "")
                + "</li>"
                for link in links
            )
            return f"<ol>{inner}</ol>"

        assert self.nav is not None
        return page(f'<nav epub:type="toc"><h1>Contents</h1>{render(self.nav)}</nav>')

    def _ncx(self) -> str:
        def render(links: list[TocLink]) -> str:
            return "".join(
                f"<navPoint><navLabel><text>{link.label}</text></navLabel>"
                f'<content src="{link.href}"/>{render(link.children)}</navPoint>'
                for link in links
            )

        assert self.ncx is not None
        return (
            '<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/">'
            f"<navMap>{render(self.ncx)}</navMap></ncx>"
        )
