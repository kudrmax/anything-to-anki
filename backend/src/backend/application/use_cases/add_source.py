from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from pathlib import PurePath
from typing import TYPE_CHECKING

from backend.application.constants import NAMING_RULE_SETTING
from backend.application.dto.add_source_dtos import (
    CollectionChoiceDTO,
    NamingItemDTO,
    NamingRequired,
    NamingVariableDTO,
    NumberFormatDTO,
    QuestionDTO,
    QuestionsRequired,
)
from backend.application.source_intake.book_handler import UNTITLED_BOOK
from backend.application.source_intake.document_normalizer import EMPTY_SOURCE_MESSAGE
from backend.application.source_intake.typed_input import SUBTITLES_NEED_VIDEO_MESSAGE
from backend.application.utils.typed_path import normalize_typed_path
from backend.domain.exceptions import (
    BookReadError,
    InputFailedError,
    InvalidAnswerError,
    InvalidSourceInputError,
    NotATextFileError,
    SubtitlesNotAvailableError,
    UnsupportedUrlError,
)
from backend.domain.services.natural_order import natural_key
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.naming_rule import (
    COLLECTION_PLACEHOLDER,
    DEFAULT_NAMING_RULE,
    NUMBER_PLACEHOLDER,
    TITLE_PLACEHOLDER,
)
from backend.domain.value_objects.question import Answers
from backend.domain.value_objects.source_input import LocalFile, PastedText, Url

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from backend.application.dto.add_source_dtos import SourcesCreated
    from backend.application.source_intake.document_normalizer import DocumentNormalizer
    from backend.application.source_intake.kind_handler import KindHandler
    from backend.application.source_intake.naming import Naming
    from backend.application.source_intake.source_draft import SourceDraft
    from backend.application.source_intake.source_group_writer import SourceGroupWriter
    from backend.domain.ports.file_reader import FileReader
    from backend.domain.ports.format_detector import FormatDetector
    from backend.domain.ports.format_reader import FormatReader
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.value_objects.collection_choice import CollectionChoice
    from backend.domain.value_objects.content import Content, Kind
    from backend.domain.value_objects.question import Question
    from backend.domain.value_objects.source_input import SourceInput

logger = logging.getLogger(__name__)

PASTED_TEXT_LABEL = "Text"
NAMING_VARIABLES: tuple[NamingVariableDTO, ...] = (
    NamingVariableDTO(token=COLLECTION_PLACEHOLDER, label="Collection"),
    NamingVariableDTO(token=NUMBER_PLACEHOLDER, label="Number"),
    NamingVariableDTO(token=TITLE_PLACEHOLDER, label="Title from file"),
)
NUMBER_FORMATS: tuple[NumberFormatDTO, ...] = (
    NumberFormatDTO(digits=None, label="Auto"),
    NumberFormatDTO(digits=1, label="1"),
    NumberFormatDTO(digits=2, label="01"),
    NumberFormatDTO(digits=3, label="001"),
)
# What can go wrong reading one input; in a batch it is reported with the input's name.
_INPUT_ERRORS: tuple[type[Exception], ...] = (
    FileNotFoundError,
    InvalidSourceInputError,
    InvalidAnswerError,
    BookReadError,
    NotATextFileError,
    UnsupportedUrlError,
    SubtitlesNotAvailableError,
)


@dataclass(frozen=True)
class _Read:
    """One input read up to its drafts, or the questions it still asks."""

    label: str
    pending: tuple[QuestionDTO, ...] = ()
    drafts: tuple[SourceDraft, ...] = ()
    name: str = UNTITLED_BOOK


class AddSourceUseCase:
    """Turns pasted text, files or a link into sources.

    The reader of each input's format reads it into content, the handler of the content's
    kind makes drafts of sources. Whatever either needs the user to choose comes back as
    questions; an add that makes several sources asks how to name them. The next call brings
    every answer so far and starts over.
    """

    def __init__(
        self,
        detector: FormatDetector,
        readers: Iterable[FormatReader],
        handlers: Iterable[KindHandler],
        normalizer: DocumentNormalizer,
        file_reader: FileReader,
        group_writer: SourceGroupWriter,
        settings_repo: SettingsRepository,
    ) -> None:
        self._detector = detector
        self._readers: dict[Format, FormatReader] = {reader.format: reader for reader in readers}
        self._handlers: dict[Kind, KindHandler] = {handler.kind: handler for handler in handlers}
        self._normalizer = normalizer
        self._file_reader = file_reader
        self._group_writer = group_writer
        self._settings_repo = settings_repo

    def execute(
        self,
        inputs: Sequence[SourceInput],
        title: str | None = None,
        answers: Sequence[Answers] = (),
        naming: Naming | None = None,
    ) -> QuestionsRequired | NamingRequired | SourcesCreated:
        batch = len(inputs) > 1
        if len(answers) > len(inputs):
            msg = f"Got more answers than inputs: {len(answers)} for {len(inputs)}"
            raise InvalidAnswerError(msg)
        labels = _labels(inputs)
        reads = [
            self._read_one(index, source_input, label, None if batch else title, answers, batch)
            for index, (source_input, label) in enumerate(zip(inputs, labels, strict=True))
        ]
        pending = _shared([question for read in reads for question in read.pending])
        if pending:
            return QuestionsRequired(questions=pending)
        if batch:
            reads.sort(key=lambda read: natural_key(read.label))
        drafts = [draft for read in reads for draft in read.drafts]
        if len(drafts) == 1:
            return self._group_writer.write_one(drafts[0], None)
        if naming is None:
            return self._naming_required(drafts, reads, batch)
        collection_name = self._group_writer.name_of(naming.collection)
        width = naming.number_format.width(len(drafts))
        titles = [
            naming.titles.get(index, "").strip()
            or naming.rule.render(collection_name, index + 1, draft.own_title or "", width)
            for index, draft in enumerate(drafts)
        ]
        return self._group_writer.write_group(drafts, naming.collection, titles)

    def _read_one(
        self,
        index: int,
        source_input: SourceInput,
        label: str,
        title: str | None,
        answers: Sequence[Answers],
        batch: bool,
    ) -> _Read:
        given = answers[index] if index < len(answers) else Answers()
        try:
            return self._read(index, source_input, label, title, given, batch)
        except _INPUT_ERRORS as e:
            if batch:
                raise InputFailedError(label, e) from e
            raise

    def _read(
        self,
        index: int,
        source_input: SourceInput,
        label: str,
        title: str | None,
        answers: Answers,
        batch: bool,
    ) -> _Read:
        source_input = self._checked_input(source_input)
        source_format = self._detector.detect(source_input)
        attaches_subtitles = (
            isinstance(source_input, LocalFile) and source_input.subtitles_path is not None
        )
        if attaches_subtitles and source_format is not Format.VIDEO_FILE:
            raise InvalidSourceInputError(SUBTITLES_NEED_VIDEO_MESSAGE)
        input_label = label if batch else None

        reader = self._readers[source_format]
        asked = list(reader.questions(source_input))
        if pending := _pending(asked, answers, index, input_label):
            return _Read(label=label, pending=pending)
        content = self._normalizer.normalize(reader.read(source_input, answers))
        if title and title.strip():
            content = _titled(content, title.strip())

        handler = self._handlers[content.kind]
        asked += handler.questions(content)
        if pending := _pending(asked, answers, index, input_label):
            return _Read(label=label, pending=pending)
        _reject_unasked(asked, answers)
        drafts = handler.drafts(content, answers, source_format, label)
        return _Read(label=label, drafts=drafts, name=content.title or UNTITLED_BOOK)

    def _naming_required(
        self, drafts: Sequence[SourceDraft], reads: Sequence[_Read], batch: bool,
    ) -> NamingRequired:
        default_collection: CollectionChoice | None = None
        if batch:
            heading = f"Add {len(reads)} files"
        else:
            heading = f"Add «{reads[0].name}»"
            default_collection = self._group_writer.resolve(reads[0].name)
        return NamingRequired(
            heading=heading,
            items=[
                NamingItemDTO(label=d.label, own_title=d.own_title or "", words=d.words)
                for d in drafts
            ],
            default_collection=(
                CollectionChoiceDTO(
                    existing_id=default_collection.existing_id,
                    new_name=default_collection.new_name,
                )
                if default_collection
                else None
            ),
            default_rule=self._settings_repo.get(NAMING_RULE_SETTING) or DEFAULT_NAMING_RULE,
            variables=list(NAMING_VARIABLES),
            number_formats=list(NUMBER_FORMATS),
        )

    def _checked_input(self, source_input: SourceInput) -> SourceInput:
        match source_input:
            case PastedText():
                if not source_input.text.strip():
                    raise InvalidSourceInputError(EMPTY_SOURCE_MESSAGE)
            case LocalFile():
                source_input = LocalFile(
                    path=normalize_typed_path(source_input.path),
                    subtitles_path=(
                        normalize_typed_path(source_input.subtitles_path)
                        if source_input.subtitles_path
                        else None
                    ),
                )
                if not self._file_reader.exists(source_input.path):
                    msg = f"File not found: {source_input.path}"
                    raise FileNotFoundError(msg)
        return source_input


def _pending(
    asked: list[Question], answers: Answers, index: int, input_label: str | None,
) -> tuple[QuestionDTO, ...]:
    for question in asked:
        answer = answers.get(question.id)
        if answer is not None and answer not in question.option_ids:
            msg = f"{answer!r} is not an option of {question.id!r}"
            raise InvalidAnswerError(msg)
    return tuple(
        QuestionDTO.from_question(question, index, input_label)
        for question in asked
        if not answers.has(question.id)
    )


def _reject_unasked(asked: list[Question], answers: Answers) -> None:
    unasked = set(answers.chosen) - {question.id for question in asked}
    if unasked:
        msg = f"Answers to questions that weren't asked: {', '.join(sorted(unasked))}"
        raise InvalidAnswerError(msg)


def _shared(questions: Sequence[QuestionDTO]) -> list[QuestionDTO]:
    """The same question about several inputs is asked once; its answer goes to each."""
    shared: list[QuestionDTO] = []
    for question in questions:
        same = next((q for q in shared if q.same_as(question)), None)
        if same is None:
            shared.append(question.model_copy())
            continue
        same.input_indexes = [*same.input_indexes, *question.input_indexes]
        same.input_label = None
    return shared


def _labels(inputs: Sequence[SourceInput]) -> list[str]:
    """Each input's name; files of the same name are told apart by their folder."""
    names = [_label(source_input) for source_input in inputs]
    return [
        _label(source_input, with_folder=True) if names.count(name) > 1 else name
        for source_input, name in zip(inputs, names, strict=True)
    ]


def _label(source_input: SourceInput, *, with_folder: bool = False) -> str:
    match source_input:
        case LocalFile():
            path = PurePath(normalize_typed_path(source_input.path))
            return f"{path.parent.name}/{path.name}" if with_folder else path.name
        case Url():
            return source_input.url
        case PastedText():
            return PASTED_TEXT_LABEL


def _titled(content: Content, title: str) -> Content:
    return replace(content, title=title)
