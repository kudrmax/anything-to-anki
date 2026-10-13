from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.dto.add_source_dtos import QuestionsRequired, SourcesCreated
from backend.application.source_intake.book_handler import BookHandler
from backend.application.source_intake.document_normalizer import DocumentNormalizer
from backend.application.source_intake.single_source_handler import SingleSourceHandler
from backend.application.source_intake.source_writer import SourceWriter
from backend.application.use_cases.add_source import AddSourceUseCase
from backend.domain.exceptions import (
    InvalidAnswerError,
    InvalidSourceInputError,
    NotATextFileError,
    SubtitlesNotAvailableError,
)
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    Paragraph,
    ParagraphMode,
)
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.question import Answers
from backend.domain.value_objects.source_input import LocalFile, PastedText, Url
from backend.infrastructure.adapters.local_file_reader import LocalFileReader
from backend.infrastructure.adapters.regex_format_detector import RegexFormatDetector
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner
from backend.infrastructure.adapters.slang_normalizer import SlangNormalizer
from backend.infrastructure.adapters.video_path_resolver import VideoPathResolverImpl
from backend.infrastructure.persistence.sqla_collection_repository import (
    SqlaCollectionRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.readers.epub_format_reader import EpubFormatReader
from backend.infrastructure.readers.html_reader import HtmlReader
from backend.infrastructure.readers.markdown_reader import MarkdownReader
from backend.infrastructure.readers.plain_reader import PlainReader
from backend.infrastructure.readers.srt_reader import SrtReader
from backend.infrastructure.readers.video_file_reader import VideoFileReader
from backend.infrastructure.readers.youtube_reader import YouTubeReader

from tests.unit.infrastructure.epub.epub_builder import EpubBuilder, TocLink, page, prose
from tests.unit.infrastructure.readers.fakes import (
    YOUTUBE_URL,
    FakeVideoTracks,
    FakeYouTube,
    srt,
)

if TYPE_CHECKING:
    from pathlib import Path

    from backend.domain.value_objects.fetched_subtitles import FetchedSubtitles
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

TEXT = Answers({"text.kind": "text"})
SONG = Answers({"text.kind": "song"})


@pytest.fixture()
def add_source(db_session: Session, tmp_path: Path) -> AddSourceUseCase:
    files = LocalFileReader()
    tracks = FakeVideoTracks({0: srt((1, "From the video"))}, audio_tracks=2)
    youtube = FakeYouTube(srt((1, "Welcome back")))
    writer = SourceWriter(
        SqlaSourceRepository(db_session),
        SqlaDocumentRepository(db_session),
        VideoPathResolverImpl(data_dir=str(tmp_path)),
    )
    return AddSourceUseCase(
        detector=RegexFormatDetector(youtube),
        readers=(
            PlainReader(files),
            MarkdownReader(files),
            HtmlReader(files),
            EpubFormatReader(),
            SrtReader(files),
            VideoFileReader(files, tracks, tracks),
            YouTubeReader(youtube),
        ),
        handlers=(
            SingleSourceHandler(Kind.TEXT, writer),
            SingleSourceHandler(Kind.SONG, writer),
            SingleSourceHandler(Kind.SUBTITLES, writer),
            BookHandler(
                writer, SqlaCollectionRepository(db_session), SqlaSettingsRepository(db_session),
            ),
        ),
        normalizer=DocumentNormalizer(RegexTextCleaner(), SlangNormalizer()),
        file_reader=files,
    )


def _created(result: QuestionsRequired | SourcesCreated) -> SourcesCreated:
    assert isinstance(result, SourcesCreated), result
    return result


def _asked(result: QuestionsRequired | SourcesCreated) -> list[str]:
    assert isinstance(result, QuestionsRequired), result
    return [question.id for question in result.questions]


def _book(tmp_path: Path, chapters: int) -> str:
    book = EpubBuilder(title="Flourish")
    for n in range(1, chapters + 1):
        book.add(f"c{n}.xhtml", page(f"<h1>Chapter {n}</h1><p>{prose(100 * n + 100)}</p>"))
    book.nav = [TocLink(f"Chapter {n}", f"c{n}.xhtml") for n in range(1, chapters + 1)]
    return str(book.write(tmp_path / "flourish.epub"))


class TestText:
    def test_asks_text_or_song_first(self, add_source: AddSourceUseCase) -> None:
        assert _asked(add_source.execute(PastedText("Hello there."))) == ["text.kind"]

    def test_text_becomes_one_source_with_its_document(
        self, add_source: AddSourceUseCase, db_session: Session,
    ) -> None:
        created = _created(add_source.execute(PastedText("I wanna go.\n\nNow."), answers=TEXT))

        (source_id,) = created.source_ids
        source = SqlaSourceRepository(db_session).get_by_id(source_id)
        assert source is not None
        assert (source.format, source.kind) == (Format.PLAIN, Kind.TEXT)
        assert source.title == "I want to go.\n\nNow."
        assert SqlaDocumentRepository(db_session).get(source_id) == Document((
            Paragraph((Line("I want to go."),), ParagraphMode.FLOW),
            Paragraph((Line("Now."),), ParagraphMode.FLOW),
        ))

    def test_song_drops_lines_with_nothing_to_read(
        self, add_source: AddSourceUseCase, db_session: Session,
    ) -> None:
        text = "[Chorus]\nHello darkness\n♪\nmy old friend"
        (source_id,) = _created(add_source.execute(PastedText(text), answers=SONG)).source_ids
        source = SqlaSourceRepository(db_session).get_by_id(source_id)
        assert source is not None
        assert source.kind is Kind.SONG
        assert SqlaDocumentRepository(db_session).get(source_id) == Document((
            Paragraph((Line("Hello darkness"), Line("my old friend")), ParagraphMode.LINES),
        ))

    def test_own_title_wins(self, add_source: AddSourceUseCase, db_session: Session) -> None:
        result = add_source.execute(PastedText("Text."), title="  Mine ", answers=TEXT)
        source = SqlaSourceRepository(db_session).get_by_id(_created(result).source_ids[0])
        assert source is not None
        assert source.title == "Mine"

    def test_markdown_file_keeps_headings(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        path = tmp_path / "notes.md"
        path.write_text("# Notes\n\nText here.")
        result = add_source.execute(LocalFile(f"'{path}'"), answers=TEXT)
        (source_id,) = _created(result).source_ids
        source = SqlaSourceRepository(db_session).get_by_id(source_id)
        assert source is not None
        assert (source.title, source.format) == ("notes", Format.MARKDOWN)
        document = SqlaDocumentRepository(db_session).get(source_id)
        assert document is not None
        assert document.blocks[0] == Heading(1, "Notes")


class TestErrors:
    @pytest.mark.parametrize("text", ["", "  \n "])
    def test_empty_text(self, add_source: AddSourceUseCase, text: str) -> None:
        with pytest.raises(InvalidSourceInputError, match="cannot be empty"):
            add_source.execute(PastedText(text))

    def test_text_left_empty_after_cleaning(self, add_source: AddSourceUseCase) -> None:
        with pytest.raises(InvalidSourceInputError, match="cannot be empty"):
            add_source.execute(PastedText("[Chorus]\n♪"), answers=SONG)

    def test_answer_that_is_not_an_option(self, add_source: AddSourceUseCase) -> None:
        with pytest.raises(InvalidAnswerError):
            add_source.execute(PastedText("Hi."), answers=Answers({"text.kind": "poem"}))

    def test_answer_to_a_question_not_asked(self, add_source: AddSourceUseCase) -> None:
        answers = Answers({"text.kind": "text", "book.split": "split"})
        with pytest.raises(InvalidAnswerError, match="book.split"):
            add_source.execute(PastedText("Hi."), answers=answers)

    def test_missing_file(self, add_source: AddSourceUseCase, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            add_source.execute(LocalFile(str(tmp_path / "nope.txt")))

    def test_binary_file(self, add_source: AddSourceUseCase, tmp_path: Path) -> None:
        path = tmp_path / "image.png"
        path.write_bytes(b"\x89PNG\x00\x00binary")
        with pytest.raises(NotATextFileError):
            add_source.execute(LocalFile(str(path)), answers=TEXT)

    def test_srt_attached_to_something_else(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        path = tmp_path / "notes.txt"
        path.write_text("Text")
        with pytest.raises(InvalidSourceInputError, match="only be attached to a video"):
            add_source.execute(LocalFile(str(path), subtitles_path=str(path)))


class TestBook:
    def test_asks_to_split_showing_the_chapters(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        result = add_source.execute(LocalFile(_book(tmp_path, 2)))

        assert isinstance(result, QuestionsRequired)
        (question,) = result.questions
        assert (question.id, question.prompt, question.default) == (
            "book.split", "Add «Flourish» as", "split",
        )
        split, whole = question.options
        assert split.label == "2 chapters · 201–301 words each"
        assert split.details is not None
        assert split.details.title == "Sources in collection «Flourish»"
        assert [(item.text, item.note) for item in split.details.items] == [
            ("Flourish ch1", "201 words"),
            ("Flourish ch2", "301 words"),
        ]
        assert whole.label == "One source · 502 words"

    def test_split_book_goes_to_its_collection_again_and_again(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        path = _book(tmp_path, 2)
        split = Answers({"book.split": "split"})
        first = _created(add_source.execute(LocalFile(path), answers=split))
        again = _created(add_source.execute(LocalFile(path), answers=split))

        assert first.collection_id is not None
        assert again.collection_id == first.collection_id
        sources = [SqlaSourceRepository(db_session).get_by_id(i) for i in first.source_ids]
        assert [(s.title, s.kind, s.format) for s in sources if s] == [
            ("Flourish ch1", Kind.BOOK, Format.EPUB),
            ("Flourish ch2", Kind.BOOK, Format.EPUB),
        ]
        assert sources[0] and sources[1] and sources[0].created_at == sources[1].created_at

    def test_whole_book_is_one_document(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        result = add_source.execute(
            LocalFile(_book(tmp_path, 2)), title="Mine", answers=Answers({"book.split": "whole"}),
        )
        created = _created(result)
        assert created.collection_id is None
        (source_id,) = created.source_ids
        document = SqlaDocumentRepository(db_session).get(source_id)
        assert document is not None
        assert [b for b in document.blocks if isinstance(b, Heading)] == [
            Heading(1, "Chapter 1"), Heading(1, "Chapter 2"),
        ]
        source = SqlaSourceRepository(db_session).get_by_id(source_id)
        assert source is not None
        assert source.title == "Mine"

    def test_book_of_one_chapter_asks_nothing(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        assert len(_created(add_source.execute(LocalFile(_book(tmp_path, 1)))).source_ids) == 1


class TestVideo:
    def test_video_file_asks_for_audio_and_keeps_the_video(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        video = LocalFile(str(tmp_path / "Movie.mkv"))
        (tmp_path / "Movie.mkv").write_bytes(b"\x00")
        assert _asked(add_source.execute(video)) == ["video.audio_track"]

        result = add_source.execute(video, answers=Answers({"video.audio_track": "1"}))
        source = SqlaSourceRepository(db_session).get_by_id(_created(result).source_ids[0])
        assert source is not None
        assert (source.format, source.kind, source.title) == (
            Format.VIDEO_FILE, Kind.SUBTITLES, "Movie.mkv",
        )
        assert (source.video_path, source.audio_track_index) == (video.path, 1)

    def test_youtube_link(self, add_source: AddSourceUseCase, db_session: Session) -> None:
        result = add_source.execute(Url(YOUTUBE_URL))
        source = SqlaSourceRepository(db_session).get_by_id(_created(result).source_ids[0])
        assert source is not None
        assert (source.format, source.kind, source.title, source.source_url) == (
            Format.YOUTUBE, Kind.SUBTITLES, "A talk", YOUTUBE_URL,
        )
        assert source.video_path is None


class TestTitles:
    def test_untitled_text_is_named_by_its_start(
        self, add_source: AddSourceUseCase, db_session: Session,
    ) -> None:
        text = "word " * 40
        result = add_source.execute(PastedText(text), title="   ", answers=TEXT)
        source = SqlaSourceRepository(db_session).get_by_id(_created(result).source_ids[0])
        assert source is not None
        assert source.title == ("word " * 20)[:100]

    def test_chapters_are_named_by_the_template_setting(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        SqlaSettingsRepository(db_session).set(
            "book_chapter_title_template", "{{n}}. {{chapter_title}} ({{book_name}})",
        )
        result = add_source.execute(
            LocalFile(_book(tmp_path, 2)), answers=Answers({"book.split": "split"}),
        )
        titles = [
            source.title
            for source_id in _created(result).source_ids
            if (source := SqlaSourceRepository(db_session).get_by_id(source_id))
        ]
        assert titles == ["1. Chapter 1 (Flourish)", "2. Chapter 2 (Flourish)"]

    def test_html_file_is_text_named_after_the_file(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        path = tmp_path / "Article.html"
        path.write_text("<html><body><h1>News</h1><p>Text.</p></body></html>")
        result = add_source.execute(LocalFile(str(path)), answers=TEXT)
        source = SqlaSourceRepository(db_session).get_by_id(_created(result).source_ids[0])
        assert source is not None
        assert (source.title, source.format, source.kind) == ("Article", Format.HTML, Kind.TEXT)


def test_youtube_without_subtitles_is_reported(db_session: Session, tmp_path: Path) -> None:
    class _NoSubtitles(FakeYouTube):
        def fetch_subtitles(self, url: str, language: str = "en") -> FetchedSubtitles:
            raise SubtitlesNotAvailableError("No subtitles")

    youtube = _NoSubtitles()
    writer = SourceWriter(
        SqlaSourceRepository(db_session),
        SqlaDocumentRepository(db_session),
        VideoPathResolverImpl(data_dir=str(tmp_path)),
    )
    use_case = AddSourceUseCase(
        detector=RegexFormatDetector(youtube),
        readers=(YouTubeReader(youtube),),
        handlers=(SingleSourceHandler(Kind.SUBTITLES, writer),),
        normalizer=DocumentNormalizer(RegexTextCleaner(), SlangNormalizer()),
        file_reader=LocalFileReader(),
    )
    with pytest.raises(SubtitlesNotAvailableError):
        use_case.execute(Url(YOUTUBE_URL))
