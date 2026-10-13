from __future__ import annotations

from pathlib import Path

from backend.infrastructure.epub.chapters import ChapterAssembler
from backend.infrastructure.epub.errors import EpubError
from backend.infrastructure.epub.models import DocumentText, EpubBook
from backend.infrastructure.epub.package import EpubPackage
from backend.infrastructure.epub.xhtml_text import XhtmlTextExtractor


class EpubReader:
    """Reads the prose of an epub book, chapter by chapter."""

    def __init__(self) -> None:
        self._extractor = XhtmlTextExtractor()
        self._assembler = ChapterAssembler()

    def read(self, path: str) -> EpubBook:
        package = EpubPackage.open(path)
        documents: list[tuple[str, DocumentText]] = []
        for document in package.documents():
            markup = package.read(document)
            if markup is not None:
                documents.append((document, self._extractor.extract(markup)))
        chapters = self._assembler.assemble(documents, package.toc())
        if not chapters:
            raise EpubError(f"No readable text in the book: {Path(path).name}")
        return EpubBook(title=package.title, chapters=tuple(chapters))
