from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.source_intake.book_handler import (
    SPLIT_OPTION_ID,
    SPLIT_QUESTION_ID,
    BookHandler,
)
from backend.application.source_intake.source_writer import SourceWriter
from backend.domain.entities.collection import Collection
from backend.domain.ports.settings_repository import SettingsRepository
from backend.domain.value_objects.content import BookContent, Chapter
from backend.domain.value_objects.document import Document
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.question import Answers

from tests.unit.application.collection_fakes import InMemoryCollectionRepository

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.value_objects.content import Kind, VideoRef

pytestmark = pytest.mark.unit

SPLIT = Answers({SPLIT_QUESTION_ID: SPLIT_OPTION_ID})


class _Settings(SettingsRepository):
    def get(self, key: str, default: str | None = None) -> str | None:
        return default

    def set(self, key: str, value: str) -> None:
        raise NotImplementedError


class _RecordingWriter(SourceWriter):
    def __init__(self) -> None:
        self.collection_ids: list[int | None] = []

    def write(
        self,
        *,
        document: Document,
        title: str | None,
        source_format: Format,
        kind: Kind,
        video: VideoRef | None = None,
        collection_id: int | None = None,
        created_at: datetime | None = None,
    ) -> int:
        self.collection_ids.append(collection_id)
        return len(self.collection_ids)


def _book(title: str) -> BookContent:
    chapters = tuple(Chapter(title=f"c{n}", document=Document(blocks=())) for n in (1, 2))
    return BookContent(title=title, chapters=chapters)


def _add(collections: InMemoryCollectionRepository, title: str) -> _RecordingWriter:
    writer = _RecordingWriter()
    BookHandler(writer, collections, _Settings()).create(_book(title), SPLIT, Format.EPUB)
    return writer


class TestBookCollection:
    def test_book_joins_top_level_collection_ignoring_case(self) -> None:
        collections = InMemoryCollectionRepository([Collection(id=1, name="dune")])

        writer = _add(collections, "Dune")

        assert set(writer.collection_ids) == {1}
        assert len(collections.list_all()) == 1

    def test_subcollection_with_same_name_is_not_joined(self) -> None:
        collections = InMemoryCollectionRepository([
            Collection(id=1, name="Herbert"), Collection(id=2, name="Dune", parent_id=1),
        ])

        _add(collections, "Dune")

        new = next(c for c in collections.list_all() if c.id not in (1, 2))
        assert (new.name, new.parent_id, new.position) == ("Dune", None, 1)
