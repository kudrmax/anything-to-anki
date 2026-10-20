from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.source_intake.source_draft import SourceDraft
from backend.application.source_intake.source_group_writer import SourceGroupWriter
from backend.application.source_intake.source_writer import SourceWriter
from backend.domain.entities.collection import Collection
from backend.domain.value_objects.collection_choice import CollectionChoice
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import Document
from backend.domain.value_objects.format import Format

from tests.unit.application.collection_fakes import InMemoryCollectionRepository

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.value_objects.content import VideoRef

pytestmark = pytest.mark.unit


class _RecordingWriter(SourceWriter):
    def __init__(self) -> None:
        self.titles: list[str | None] = []
        self.collection_ids: list[int | None] = []
        self.created_at: list[datetime | None] = []

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
        self.titles.append(title)
        self.collection_ids.append(collection_id)
        self.created_at.append(created_at)
        return len(self.titles)


def _draft(own_title: str | None) -> SourceDraft:
    return SourceDraft(
        document=Document(blocks=()), kind=Kind.TEXT, source_format=Format.PLAIN,
        own_title=own_title, label=f"{own_title}.txt", words=0,
    )


type _Setup = tuple[SourceGroupWriter, _RecordingWriter, InMemoryCollectionRepository]


def _setup(*collections: Collection) -> _Setup:
    writer = _RecordingWriter()
    repo = InMemoryCollectionRepository(collections)
    return SourceGroupWriter(writer, repo), writer, repo


TWO = (_draft("a"), _draft("b"))


class TestWriteOne:
    def test_given_title_wins(self) -> None:
        group, writer, _ = _setup()
        group.write_one(_draft("own"), "Given")
        assert writer.titles == ["Given"]

    def test_own_title_without_given(self) -> None:
        group, writer, _ = _setup()
        result = group.write_one(_draft("own"), None)
        assert writer.titles == ["own"]
        assert (result.source_ids, result.collection_id) == ([1], None)


class TestWriteGroup:
    def test_titles_in_order_and_one_moment(self) -> None:
        group, writer, _ = _setup()
        group.write_group(TWO, CollectionChoice(), ["A1", "B2"])
        assert writer.titles == ["A1", "B2"]
        assert writer.collection_ids == [None, None]
        assert len(set(writer.created_at)) == 1
        assert writer.created_at[0] is not None

    def test_existing_collection_is_used(self) -> None:
        group, writer, _ = _setup(Collection(id=7, name="Dune"))
        result = group.write_group(TWO, CollectionChoice(existing_id=7), ["1", "2"])
        assert writer.collection_ids == [7, 7]
        assert result.collection_id == 7

    def test_new_name_creates_top_level_collection_last(self) -> None:
        group, writer, repo = _setup(Collection(id=1, name="Herbert"))
        group.write_group(TWO, CollectionChoice(new_name=" Dune "), ["1", "2"])
        new = next(c for c in repo.list_all() if c.id != 1)
        assert (new.name, new.parent_id, new.position) == ("Dune", None, 1)
        assert writer.collection_ids == [new.id, new.id]

    def test_new_name_joins_top_level_collection_ignoring_case(self) -> None:
        group, writer, repo = _setup(Collection(id=1, name="dune"))
        group.write_group(TWO, CollectionChoice(new_name="Dune"), ["1", "2"])
        assert writer.collection_ids == [1, 1]
        assert len(repo.list_all()) == 1

    def test_subcollection_with_same_name_is_not_joined(self) -> None:
        group, writer, repo = _setup(
            Collection(id=1, name="Herbert"), Collection(id=2, name="Dune", parent_id=1),
        )
        group.write_group(TWO, CollectionChoice(new_name="Dune"), ["1", "2"])
        assert writer.collection_ids[0] not in (1, 2)
        assert len(repo.list_all()) == 3


class TestResolve:
    def test_existing_top_level_name_resolves_to_its_id(self) -> None:
        group, _, _ = _setup(Collection(id=4, name="Dune"))
        assert group.resolve("dune") == CollectionChoice(existing_id=4)

    def test_unknown_name_resolves_to_new(self) -> None:
        group, _, _ = _setup()
        assert group.resolve("Dune") == CollectionChoice(new_name="Dune")
