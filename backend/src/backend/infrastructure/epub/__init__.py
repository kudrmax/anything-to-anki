"""Reading the prose of epub books.

Self-contained: depends only on the standard library and knows nothing about the rest of the app.
"""

from backend.infrastructure.epub.errors import EpubError
from backend.infrastructure.epub.models import EpubBook, EpubChapter
from backend.infrastructure.epub.reader import EpubReader

__all__ = ["EpubBook", "EpubChapter", "EpubError", "EpubReader"]
