from unittest.mock import MagicMock

import pytest
from backend.application.dto.book_dtos import BookSourcesCreated, BookSplitRequired
from backend.application.use_cases.create_book_sources import CreateBookSourcesUseCase
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.ports.book_reader import BookReader
from backend.domain.ports.collection_repository import CollectionRepository
from backend.domain.ports.settings_repository import SettingsRepository
from backend.domain.ports.source_repository import SourceRepository
from backend.domain.value_objects.book import Book, BookChapter
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod

BOOK = Book(
    title="Dune",
    chapters=(
        BookChapter(title="Arrakis", text="First chapter.", word_count=1200),
        BookChapter(title=None, text="Second chapter.", word_count=800),
    ),
)


@pytest.mark.unit
class TestCreateBookSourcesUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock(spec=SourceRepository)
        self.source_repo.create.side_effect = self._stored
        self.collection_repo = MagicMock(spec=CollectionRepository)
        self.collection_repo.list_all.return_value = []
        self.collection_repo.create.side_effect = lambda c: Collection(name=c.name, id=7)
        self.settings_repo = MagicMock(spec=SettingsRepository)
        self.settings_repo.get.side_effect = lambda key, default=None: default
        self.book_reader = MagicMock(spec=BookReader)
        self.book_reader.read.return_value = BOOK
        self.use_case = CreateBookSourcesUseCase(
            source_repo=self.source_repo,
            collection_repo=self.collection_repo,
            settings_repo=self.settings_repo,
            book_reader=self.book_reader,
        )
        self.created: list[Source] = []

    def _stored(self, source: Source) -> Source:
        self.created.append(source)
        source.id = len(self.created)
        return source

    def test_asks_whether_to_split_a_book_of_several_chapters(self) -> None:
        result = self.use_case.execute("/books/dune.epub", None, None)

        assert isinstance(result, BookSplitRequired)
        assert result.book_name == "Dune"
        assert result.word_count == 2000
        assert [(c.title, c.word_count) for c in result.chapters] == [
            ("Dune ch1", 1200), ("Dune ch2", 800),
        ]
        self.source_repo.create.assert_not_called()

    def test_split_book_becomes_chapter_sources_in_a_collection(self) -> None:
        result = self.use_case.execute("/books/dune.epub", "My Dune", True)

        assert result == BookSourcesCreated(source_ids=[1, 2], collection_id=7)
        assert self.collection_repo.create.call_args[0][0].name == "My Dune"
        assert [(s.title, s.raw_text, s.collection_id) for s in self.created] == [
            ("My Dune ch1", "First chapter.", 7), ("My Dune ch2", "Second chapter.", 7),
        ]
        assert all(s.input_method == InputMethod.BOOK_FILE for s in self.created)
        assert all(s.content_type == ContentType.TEXT for s in self.created)

    def test_book_added_again_joins_its_collection(self) -> None:
        self.collection_repo.list_all.return_value = [Collection(name="Dune", id=3)]

        result = self.use_case.execute("/books/dune.epub", None, True)

        assert isinstance(result, BookSourcesCreated)
        assert result.collection_id == 3
        self.collection_repo.create.assert_not_called()

    def test_chapter_titles_follow_the_template_setting(self) -> None:
        self.settings_repo.get.side_effect = lambda key, default=None: "{{n}} · {{chapter_title}}"

        self.use_case.execute("/books/dune.epub", None, True)

        assert [s.title for s in self.created] == ["1 · Arrakis", "2 · Chapter 2"]

    def test_whole_book_is_one_source_without_collection(self) -> None:
        result = self.use_case.execute("/books/dune.epub", None, False)

        assert result == BookSourcesCreated(source_ids=[1], collection_id=None)
        assert self.created[0].title == "Dune"
        assert self.created[0].raw_text == "First chapter.\n\nSecond chapter."
        self.collection_repo.create.assert_not_called()

    def test_single_chapter_book_needs_no_choice(self) -> None:
        self.book_reader.read.return_value = Book(title=None, chapters=BOOK.chapters[:1])

        result = self.use_case.execute("/books/short-story.epub", None, None)

        assert result == BookSourcesCreated(source_ids=[1], collection_id=None)
        assert self.created[0].title == "short-story"
