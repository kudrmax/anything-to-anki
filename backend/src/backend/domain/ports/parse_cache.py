from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData


class ParseCache(ABC):
    """Parses of documents kept for later: by the document's hash and the analyzer's version."""

    @abstractmethod
    def get(self, document_hash: str, analyzer_version: str) -> list[TokenData] | None: ...

    @abstractmethod
    def put(self, document_hash: str, analyzer_version: str, tokens: list[TokenData]) -> None: ...

    @abstractmethod
    def keep_only(self, document_hashes: set[str]) -> int:
        """Drops the parses of every other document; returns how many were dropped."""
