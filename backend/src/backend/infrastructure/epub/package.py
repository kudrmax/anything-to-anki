from __future__ import annotations

import posixpath
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import TYPE_CHECKING
from urllib.parse import unquote
from xml.etree import ElementTree

from backend.infrastructure.epub.errors import EpubError
from backend.infrastructure.epub.models import TocEntry
from backend.infrastructure.epub.xhtml_text import normalized, semantic_types

if TYPE_CHECKING:
    from collections.abc import Iterator

CONTAINER_PATH = "META-INF/container.xml"
DOCUMENT_EXTENSIONS: tuple[str, ...] = (".xhtml", ".html", ".htm")
DOCUMENT_MEDIA_TYPES: frozenset[str] = frozenset({"application/xhtml+xml", "text/html"})
NCX_MEDIA_TYPE = "application/x-dtbncx+xml"
NAV_PROPERTY = "nav"
TOC_TYPE = "toc"
NON_LINEAR = "no"
LIST_TAGS: frozenset[str] = frozenset({"ol", "ul"})

_DECLARED_ENCODING_RE = re.compile(rb"""encoding=["']([\w.:-]+)["']""")
_DECLARATION_PROBE_BYTES = 256
_UTF16_BOMS: tuple[bytes, ...] = (b"\xff\xfe", b"\xfe\xff")
_FALLBACK_ENCODING = "utf-8"


def local_name(tag: object) -> str:
    """The tag without its namespace, so broken or missing namespaces don't matter."""
    return str(tag).rsplit("}", 1)[-1].lower()


def decode(raw: bytes) -> str:
    if raw.startswith(_UTF16_BOMS):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    declared = _DECLARED_ENCODING_RE.search(raw[:_DECLARATION_PROBE_BYTES])
    if declared:
        try:
            return raw.decode(declared.group(1).decode("ascii"), errors="replace")
        except LookupError:
            pass
    return raw.decode(_FALLBACK_ENCODING, errors="replace")


def split_href(base_document: str, href: str) -> tuple[str, str | None]:
    """Resolves a link relative to the document it appears in: (document path, fragment)."""
    path, _, fragment = href.partition("#")
    if path:
        document = posixpath.normpath(
            posixpath.join(posixpath.dirname(base_document), unquote(path))
        )
    else:
        document = base_document
    return document, (unquote(fragment) or None)


@dataclass(frozen=True)
class _ManifestItem:
    path: str
    media_type: str
    properties: frozenset[str]

    @property
    def is_document(self) -> bool:
        return self.media_type in DOCUMENT_MEDIA_TYPES or self.path.lower().endswith(
            DOCUMENT_EXTENSIONS
        )


class _NavTocParser(HTMLParser):
    """Links of the EPUB 3 navigation document: the toc nav, or any nav if none is marked."""

    def __init__(self, document: str) -> None:
        super().__init__(convert_charrefs=True)
        self._document = document
        self._nav_depth = 0
        self._list_depth = 0
        self._nav_is_toc = False
        self._href: str | None = None
        self._label: list[str] = []
        self.toc_entries: list[TocEntry] = []
        self.any_entries: list[TocEntry] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        if tag == "nav":
            if self._nav_depth == 0:
                self._nav_is_toc = TOC_TYPE in semantic_types(values)
            self._nav_depth += 1
        elif tag in LIST_TAGS and self._nav_depth > 0:
            self._list_depth += 1
        elif tag == "a" and self._nav_depth > 0 and values.get("href"):
            self._href = values["href"]
            self._label = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav" and self._nav_depth > 0:
            self._nav_depth -= 1
            self._list_depth = 0
        elif tag in LIST_TAGS and self._list_depth > 0:
            self._list_depth -= 1
        elif tag == "a" and self._href is not None:
            document, fragment = split_href(self._document, self._href)
            entry = TocEntry(
                label=normalized("".join(self._label)),
                document=document,
                fragment=fragment,
                depth=max(self._list_depth - 1, 0),
            )
            (self.toc_entries if self._nav_is_toc else self.any_entries).append(entry)
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._label.append(data)


class EpubPackage:
    """The parts of an epub archive that matter for reading: title, reading order and contents."""

    def __init__(self, archive: zipfile.ZipFile) -> None:
        self._archive = archive
        self._names = {name.lower(): name for name in archive.namelist()}
        self._opf_path = self._find_opf()
        self._opf = self._parse_xml(self._opf_path) if self._opf_path else None
        self._manifest = self._read_manifest()

    @classmethod
    def open(cls, path: str) -> EpubPackage:
        try:
            return cls(zipfile.ZipFile(path))
        except (zipfile.BadZipFile, OSError) as e:
            raise EpubError(f"Not an epub file: {path}") from e

    def read(self, path: str) -> str | None:
        name = self._names.get(path.lower())
        if name is None:
            return None
        return decode(self._archive.read(name))

    @property
    def title(self) -> str | None:
        for element in self._opf_elements():
            if local_name(element.tag) == "title" and element.text and element.text.strip():
                return normalized(element.text)
        return None

    def documents(self) -> list[str]:
        """Content documents in reading order; falls back to the archive's own order."""
        spine = self._spine_documents()
        if spine:
            return spine
        manifest = [item.path for item in self._manifest.values() if item.is_document]
        if manifest:
            return manifest
        return sorted(
            name for name in self._archive.namelist() if name.lower().endswith(DOCUMENT_EXTENSIONS)
        )

    def toc(self) -> list[TocEntry]:
        return self._nav_toc() or self._ncx_toc()

    def _find_opf(self) -> str | None:
        container = self._parse_xml(CONTAINER_PATH)
        if container is not None:
            for element in container.iter():
                full_path = element.get("full-path")
                if local_name(element.tag) == "rootfile" and full_path and self._exists(full_path):
                    return full_path
        return next(
            (name for name in self._archive.namelist() if name.lower().endswith(".opf")), None
        )

    def _exists(self, path: str) -> bool:
        return path.lower() in self._names

    def _parse_xml(self, path: str) -> ElementTree.Element | None:
        text = self.read(path)
        if text is None:
            return None
        try:
            return ElementTree.fromstring(text.lstrip())
        except ElementTree.ParseError:
            return None

    def _opf_elements(self) -> Iterator[ElementTree.Element]:
        if self._opf is None:
            return iter(())
        return self._opf.iter()

    def _read_manifest(self) -> dict[str, _ManifestItem]:
        manifest: dict[str, _ManifestItem] = {}
        if self._opf_path is None:
            return manifest
        for element in self._opf_elements():
            item_id, href = element.get("id"), element.get("href")
            if local_name(element.tag) != "item" or not item_id or not href:
                continue
            path, _ = split_href(self._opf_path, href)
            if self._exists(path):
                manifest[item_id] = _ManifestItem(
                    path=path,
                    media_type=(element.get("media-type") or "").lower(),
                    properties=frozenset((element.get("properties") or "").lower().split()),
                )
        return manifest

    def _spine_documents(self) -> list[str]:
        documents: list[str] = []
        for element in self._opf_elements():
            if (
                local_name(element.tag) != "itemref"
                or element.get("linear", "").lower() == NON_LINEAR
            ):
                continue
            item = self._manifest.get(element.get("idref") or "")
            if item is not None and item.is_document and item.path not in documents:
                documents.append(item.path)
        return documents

    def _nav_toc(self) -> list[TocEntry]:
        nav = next(
            (item for item in self._manifest.values() if NAV_PROPERTY in item.properties), None
        )
        markup = self.read(nav.path) if nav else None
        if nav is None or markup is None:
            return []
        parser = _NavTocParser(nav.path)
        parser.feed(markup)
        parser.close()
        return parser.toc_entries or parser.any_entries

    def _ncx_toc(self) -> list[TocEntry]:
        ncx = self._ncx_item()
        root = self._parse_xml(ncx.path) if ncx else None
        if ncx is None or root is None:
            return []
        entries: list[TocEntry] = []
        self._collect_nav_points(root, ncx.path, -1, entries)
        return entries

    def _collect_nav_points(
        self,
        element: ElementTree.Element,
        ncx_path: str,
        depth: int,
        entries: list[TocEntry],
    ) -> None:
        if local_name(element.tag) == "navpoint":
            depth += 1
            label, src = "", None
            for child in element:
                name = local_name(child.tag)
                if name == "navlabel":
                    label = normalized("".join(child.itertext()))
                elif name == "content":
                    src = child.get("src")
            if src:
                document, fragment = split_href(ncx_path, src)
                entries.append(
                    TocEntry(label=label, document=document, fragment=fragment, depth=depth)
                )
        for child in element:
            self._collect_nav_points(child, ncx_path, depth, entries)

    def _ncx_item(self) -> _ManifestItem | None:
        for element in self._opf_elements():
            if local_name(element.tag) == "spine" and element.get("toc") in self._manifest:
                return self._manifest[element.get("toc") or ""]
        return next(
            (item for item in self._manifest.values() if item.media_type == NCX_MEDIA_TYPE), None
        )
