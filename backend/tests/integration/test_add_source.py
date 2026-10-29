from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.add_source_dtos import (
    CollectionChoiceDTO,
    NamingRequired,
    QuestionsRequired,
    SourcesCreated,
)
from backend.application.source_intake.book_handler import BookHandler
from backend.application.source_intake.document_normalizer import DocumentNormalizer
from backend.application.source_intake.naming import Naming
from backend.application.source_intake.single_source_handler import SingleSourceHandler
from backend.application.source_intake.source_group_writer import SourceGroupWriter
from backend.application.source_intake.source_writer import SourceWriter
from backend.application.use_cases.add_source import AddSourceUseCase
from backend.domain.exceptions import (
    InputFailedError,
    InvalidAnswerError,
    InvalidSourceInputError,
    NotATextFileError,
    SubtitlesNotAvailableError,
)
from backend.domain.value_objects.collection_choice import CollectionChoice
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    Paragraph,
    ParagraphMode,
)
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.naming_rule import NamingRule
from backend.domain.value_objects.number_format import NumberFormat
from backend.domain.value_objects.question import Answers
from backend.domain.value_objects.source_input import LocalFile, PastedText, SourceInput, Url
from backend.infrastructure.adapters.local_file_reader import LocalFileReader
from backend.infrastructure.adapters.regex_format_detector import RegexFormatDetector
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner
from backend.infrastructure.adapters.slang_normalizer import SlangNormalizer
from backend.infrastructure.adapters.video_path_resolver import VideoPathResolverImpl
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
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
SPLIT = Answers({"book.split": "split"})
DEFAULT_RULE = "{{collection}} ch{{n}}"


@pytest.fixture()
def add_source(db_session: Session, tmp_path: Path) -> AddSourceUseCase:
    files = LocalFileReader()
    tracks = FakeVideoTracks({0: srt((1, "From the video"))}, audio_tracks=2)
    youtube = FakeYouTube(srt((1, "Welcome back")))
    writer = SourceWriter(
        SqlaSourceRepository(db_session, SessionChangeRecorder(db_session)),
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
            SingleSourceHandler(Kind.TEXT),
            SingleSourceHandler(Kind.SONG),
            SingleSourceHandler(Kind.SUBTITLES),
            BookHandler(),
        ),
        normalizer=DocumentNormalizer(RegexTextCleaner(), SlangNormalizer()),
        file_reader=files,
        group_writer=SourceGroupWriter(writer, SqlaCollectionRepository(db_session)),
        settings_repo=SqlaSettingsRepository(db_session, SessionChangeRecorder(db_session)),
        unit_of_work=MagicMock(),
    )


type _Result = QuestionsRequired | NamingRequired | SourcesCreated


def _add(
    use_case: AddSourceUseCase,
    source_input: SourceInput,
    title: str | None = None,
    answers: Answers | None = None,
    naming: Naming | None = None,
) -> _Result:
    return use_case.execute([source_input], title, [answers] if answers else [], naming)


def _created(result: _Result) -> SourcesCreated:
    assert isinstance(result, SourcesCreated), result
    return result


def _asked(result: _Result) -> list[str]:
    assert isinstance(result, QuestionsRequired), result
    return [question.id for question in result.questions]


def _naming(result: _Result) -> NamingRequired:
    assert isinstance(result, NamingRequired), result
    return result


def _book(tmp_path: Path, chapters: int) -> str:
    book = EpubBuilder(title="Flourish")
    for n in range(1, chapters + 1):
        book.add(f"c{n}.xhtml", page(f"<h1>Chapter {n}</h1><p>{prose(100 * n + 100)}</p>"))
    book.nav = [TocLink(f"Chapter {n}", f"c{n}.xhtml") for n in range(1, chapters + 1)]
    return str(book.write(tmp_path / "flourish.epub"))


class TestText:
    def test_asks_text_or_song_first(self, add_source: AddSourceUseCase) -> None:
        assert _asked(_add(add_source, PastedText("Hello there."))) == ["text.kind"]

    def test_text_becomes_one_source_with_its_document(
        self, add_source: AddSourceUseCase, db_session: Session,
    ) -> None:
        created = _created(_add(add_source, PastedText("I wanna go.\n\nNow."), answers=TEXT))

        (source_id,) = created.source_ids
        source = SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(source_id)
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
        (source_id,) = _created(_add(add_source, PastedText(text), answers=SONG)).source_ids
        source = SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(source_id)
        assert source is not None
        assert source.kind is Kind.SONG
        assert SqlaDocumentRepository(db_session).get(source_id) == Document((
            Paragraph((Line("Hello darkness"), Line("my old friend")), ParagraphMode.LINES),
        ))

    def test_own_title_wins(self, add_source: AddSourceUseCase, db_session: Session) -> None:
        result = _add(add_source, PastedText("Text."), title="  Mine ", answers=TEXT)
        source = SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(_created(result).source_ids[0])
        assert source is not None
        assert source.title == "Mine"

    def test_markdown_file_keeps_headings(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        path = tmp_path / "notes.md"
        path.write_text("# Notes\n\nText here.")
        result = _add(add_source, LocalFile(f"'{path}'"), answers=TEXT)
        (source_id,) = _created(result).source_ids
        source = SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(source_id)
        assert source is not None
        assert (source.title, source.format) == ("notes", Format.MARKDOWN)
        document = SqlaDocumentRepository(db_session).get(source_id)
        assert document is not None
        assert document.blocks[0] == Heading(1, "Notes")


class TestErrors:
    @pytest.mark.parametrize("text", ["", "  \n "])
    def test_empty_text(self, add_source: AddSourceUseCase, text: str) -> None:
        with pytest.raises(InvalidSourceInputError, match="cannot be empty"):
            _add(add_source, PastedText(text))

    def test_text_left_empty_after_cleaning(self, add_source: AddSourceUseCase) -> None:
        with pytest.raises(InvalidSourceInputError, match="cannot be empty"):
            _add(add_source, PastedText("[Chorus]\n♪"), answers=SONG)

    def test_answer_that_is_not_an_option(self, add_source: AddSourceUseCase) -> None:
        with pytest.raises(InvalidAnswerError):
            _add(add_source, PastedText("Hi."), answers=Answers({"text.kind": "poem"}))

    def test_answer_to_a_question_not_asked(self, add_source: AddSourceUseCase) -> None:
        answers = Answers({"text.kind": "text", "book.split": "split"})
        with pytest.raises(InvalidAnswerError, match="book.split"):
            _add(add_source, PastedText("Hi."), answers=answers)

    def test_missing_file(self, add_source: AddSourceUseCase, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            _add(add_source, LocalFile(str(tmp_path / "nope.txt")))

    def test_binary_file(self, add_source: AddSourceUseCase, tmp_path: Path) -> None:
        path = tmp_path / "image.png"
        path.write_bytes(b"\x89PNG\x00\x00binary")
        with pytest.raises(NotATextFileError):
            _add(add_source, LocalFile(str(path)), answers=TEXT)

    def test_srt_attached_to_something_else(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        path = tmp_path / "notes.txt"
        path.write_text("Text")
        with pytest.raises(InvalidSourceInputError, match="only be attached to a video"):
            _add(add_source, LocalFile(str(path), subtitles_path=str(path)))


class TestBook:
    def test_asks_to_split(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        result = _add(add_source, LocalFile(_book(tmp_path, 2)))

        assert isinstance(result, QuestionsRequired)
        (question,) = result.questions
        assert (question.id, question.prompt, question.default) == (
            "book.split", "Add «Flourish» as", "split",
        )
        split, whole = question.options
        assert (split.label, split.facts) == ("2 chapters", ["201–301 words each"])
        assert split.details is None
        assert (whole.label, whole.facts) == ("One source", ["502 words"])

    def test_split_book_asks_how_to_name_its_chapters(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        naming = _naming(_add(add_source, LocalFile(_book(tmp_path, 2)), answers=SPLIT))

        assert naming.heading == "Add «Flourish»"
        assert naming.default_collection == CollectionChoiceDTO(new_name="Flourish")
        assert naming.default_rule == "{{collection}} ch{{n}}"
        assert [(i.label, i.own_title, i.words) for i in naming.items] == [
            ("chapter 1", "Chapter 1", 201), ("chapter 2", "Chapter 2", 301),
        ]

    def test_split_book_goes_to_its_collection_again_and_again(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        path = _book(tmp_path, 2)
        named = Naming(CollectionChoice(new_name="Flourish"), NamingRule(DEFAULT_RULE), {})
        first = _created(_add(add_source, LocalFile(path), answers=SPLIT, naming=named))
        again = _naming(_add(add_source, LocalFile(path), answers=SPLIT))

        assert first.collection_id is not None
        assert again.default_collection == CollectionChoiceDTO(existing_id=first.collection_id)
        sources = [SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(i) for i in first.source_ids]
        assert [(s.title, s.kind, s.format) for s in sources if s] == [
            ("Flourish ch1", Kind.BOOK, Format.EPUB),
            ("Flourish ch2", Kind.BOOK, Format.EPUB),
        ]
        assert sources[0] and sources[1] and sources[0].created_at == sources[1].created_at

    def test_title_names_the_book(self, add_source: AddSourceUseCase, tmp_path: Path) -> None:
        naming = _naming(
            _add(add_source, LocalFile(_book(tmp_path, 2)), title="Mine", answers=SPLIT),
        )

        assert naming.heading == "Add «Mine»"
        assert naming.default_collection == CollectionChoiceDTO(new_name="Mine")

    def test_whole_book_is_one_document(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        result = _add(add_source,
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
        source = SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(source_id)
        assert source is not None
        assert source.title == "Mine"

    def test_book_of_one_chapter_asks_nothing(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        assert len(_created(_add(add_source, LocalFile(_book(tmp_path, 1)))).source_ids) == 1


class TestVideo:
    def test_video_file_asks_for_audio_and_keeps_the_video(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        video = LocalFile(str(tmp_path / "Movie.mkv"))
        (tmp_path / "Movie.mkv").write_bytes(b"\x00")
        assert _asked(_add(add_source, video)) == ["video.audio_track"]

        result = _add(add_source, video, answers=Answers({"video.audio_track": "1"}))
        source = SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(_created(result).source_ids[0])
        assert source is not None
        assert (source.format, source.kind, source.title) == (
            Format.VIDEO_FILE, Kind.SUBTITLES, "Movie.mkv",
        )
        assert (source.video_path, source.audio_track_index) == (video.path, 1)

    def test_youtube_link(self, add_source: AddSourceUseCase, db_session: Session) -> None:
        result = _add(add_source, Url(YOUTUBE_URL))
        source = SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(_created(result).source_ids[0])
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
        result = _add(add_source, PastedText(text), title="   ", answers=TEXT)
        source = SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(_created(result).source_ids[0])
        assert source is not None
        assert source.title == ("word " * 20)[:100]

    def test_default_rule_comes_from_the_setting(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        SqlaSettingsRepository(
            db_session, SessionChangeRecorder(db_session),
        ).set("naming_rule", "{{n}}. {{title}}")

        naming = _naming(_add(add_source, LocalFile(_book(tmp_path, 2)), answers=SPLIT))

        assert naming.default_rule == "{{n}}. {{title}}"

    def test_html_file_is_text_named_after_the_file(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        path = tmp_path / "Article.html"
        path.write_text("<html><body><h1>News</h1><p>Text.</p></body></html>")
        result = _add(add_source, LocalFile(str(path)), answers=TEXT)
        source = SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(_created(result).source_ids[0])
        assert source is not None
        assert (source.title, source.format, source.kind) == ("Article", Format.HTML, Kind.TEXT)


def test_youtube_without_subtitles_is_reported(db_session: Session, tmp_path: Path) -> None:
    class _NoSubtitles(FakeYouTube):
        def fetch_subtitles(self, url: str, language: str = "en") -> FetchedSubtitles:
            raise SubtitlesNotAvailableError("No subtitles")

    youtube = _NoSubtitles()
    writer = SourceWriter(
        SqlaSourceRepository(db_session, SessionChangeRecorder(db_session)),
        SqlaDocumentRepository(db_session),
        VideoPathResolverImpl(data_dir=str(tmp_path)),
    )
    use_case = AddSourceUseCase(
        detector=RegexFormatDetector(youtube),
        readers=(YouTubeReader(youtube),),
        handlers=(SingleSourceHandler(Kind.SUBTITLES),),
        normalizer=DocumentNormalizer(RegexTextCleaner(), SlangNormalizer()),
        file_reader=LocalFileReader(),
        group_writer=SourceGroupWriter(writer, SqlaCollectionRepository(db_session)),
        settings_repo=SqlaSettingsRepository(db_session, SessionChangeRecorder(db_session)),
        unit_of_work=MagicMock(),
    )
    with pytest.raises(SubtitlesNotAvailableError):
        _add(use_case, Url(YOUTUBE_URL))


def _files(tmp_path: Path, *names: str) -> list[SourceInput]:
    inputs: list[SourceInput] = []
    for name in names:
        path = tmp_path / name
        path.write_text(f"The story of {path.stem} begins here.")
        inputs.append(LocalFile(str(path)))
    return inputs


class TestBatch:
    def test_the_same_question_is_asked_once_for_the_batch(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        result = add_source.execute(_files(tmp_path, "a.txt", "b.txt"))

        assert isinstance(result, QuestionsRequired)
        assert [(q.id, q.input_indexes, q.input_label) for q in result.questions] == [
            ("text.kind", [0, 1], None),
        ]

    def test_different_questions_name_their_file(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        inputs = [*_files(tmp_path, "a.txt"), LocalFile(_book(tmp_path, 2))]

        result = add_source.execute(inputs)

        assert isinstance(result, QuestionsRequired)
        assert [(q.id, q.input_indexes, q.input_label) for q in result.questions] == [
            ("text.kind", [0], "a.txt"), ("book.split", [1], "flourish.epub"),
        ]

    def test_more_answers_than_inputs_are_rejected(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        with pytest.raises(InvalidAnswerError, match="more answers"):
            add_source.execute(_files(tmp_path, "a.txt", "b.txt"), answers=[TEXT, TEXT, TEXT])

    def test_same_file_names_are_told_apart_by_their_folder(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        (tmp_path / "one").mkdir()
        (tmp_path / "two").mkdir()
        inputs = _files(tmp_path, "one/notes.md", "two/notes.md")

        naming = _naming(add_source.execute(inputs, answers=[TEXT, TEXT]))

        assert [i.label for i in naming.items] == ["one/notes.md", "two/notes.md"]

    def test_blank_hand_edited_row_takes_the_rule(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        naming = Naming(CollectionChoice(), NamingRule("Part {{n}}"), {0: "  ", 1: " Intro "})

        created = _created(add_source.execute(
            _files(tmp_path, "a.txt", "b.txt"), answers=[TEXT, TEXT], naming=naming,
        ))

        sources = [SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(i) for i in created.source_ids]
        assert [s.title for s in sources if s] == ["Part 1", "Intro"]

    def test_several_sources_ask_how_to_name_them(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        inputs = _files(tmp_path, "ch10.txt", "ch2.txt")

        naming = _naming(add_source.execute(inputs, answers=[TEXT, TEXT]))

        assert naming.heading == "Add 2 files"
        assert [(i.label, i.own_title) for i in naming.items] == [
            ("ch2.txt", "ch2"), ("ch10.txt", "ch10"),
        ]
        assert naming.default_collection is None
        assert naming.default_rule == DEFAULT_RULE
        assert [(v.token, v.label) for v in naming.variables] == [
            ("{{collection}}", "Collection"),
            ("{{n}}", "Number"),
            ("{{title}}", "Title from file"),
        ]

    def test_named_sources_go_to_the_collection_in_order(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        inputs = _files(tmp_path, "ch10.txt", "ch2.txt")
        naming = Naming(
            CollectionChoice(new_name="Atomic Habits"), NamingRule(DEFAULT_RULE), {1: "Intro"},
        )

        created = _created(add_source.execute(inputs, answers=[TEXT, TEXT], naming=naming))

        sources = [SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(i) for i in created.source_ids]
        assert [s.title for s in sources if s] == ["Atomic Habits ch1", "Intro"]
        assert created.collection_id is not None
        assert {s.collection_id for s in sources if s} == {created.collection_id}

    def test_numbers_can_be_padded_to_fixed_digits(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        naming = Naming(CollectionChoice(), NamingRule("ch{{n}}"), {}, NumberFormat(digits=2))

        created = _created(add_source.execute(
            _files(tmp_path, "a.txt", "b.txt"), answers=[TEXT, TEXT], naming=naming,
        ))

        sources = [SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(i) for i in created.source_ids]
        assert [s.title for s in sources if s] == ["ch01", "ch02"]

    def test_naming_offers_number_formats_auto_first(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        inputs = _files(tmp_path, "a.txt", "b.txt")

        naming = _naming(add_source.execute(inputs, answers=[TEXT, TEXT]))

        assert [(f.digits, f.label) for f in naming.number_formats] == [
            (None, "Auto"), (1, "1"), (2, "01"), (3, "001"),
        ]

    def test_no_collection_leaves_it_out_of_titles(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        naming = Naming(CollectionChoice(), NamingRule(DEFAULT_RULE), {})

        created = _created(add_source.execute(
            _files(tmp_path, "a.txt", "b.txt"), answers=[TEXT, TEXT], naming=naming,
        ))

        sources = [SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).get_by_id(i) for i in created.source_ids]
        assert [(s.title, s.collection_id) for s in sources if s] == [("ch1", None), ("ch2", None)]

    def test_two_books_answer_separately(
        self, add_source: AddSourceUseCase, tmp_path: Path,
    ) -> None:
        first = tmp_path / "one"
        second = tmp_path / "two"
        first.mkdir()
        second.mkdir()
        inputs: list[SourceInput] = [
            LocalFile(_book(first, 2)), LocalFile(_book(second, 2)),
        ]
        whole = Answers({"book.split": "whole"})

        naming = _naming(add_source.execute(inputs, answers=[SPLIT, whole]))

        assert [i.label for i in naming.items] == ["chapter 1", "chapter 2", "two/flourish.epub"]

    def test_a_bad_file_fails_the_whole_batch_naming_it(
        self, add_source: AddSourceUseCase, db_session: Session, tmp_path: Path,
    ) -> None:
        inputs = _files(tmp_path, "a.txt")
        binary = tmp_path / "picture.txt"
        binary.write_bytes(b"\x00\x01\x02\xff")
        inputs.append(LocalFile(str(binary)))

        with pytest.raises(InputFailedError) as failed:
            add_source.execute(inputs, answers=[TEXT, TEXT])

        assert failed.value.label == "picture.txt"
        assert isinstance(failed.value.cause, NotATextFileError)
        assert SqlaSourceRepository(db_session, SessionChangeRecorder(db_session)).list_all() == []
