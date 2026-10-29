from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.exceptions import InvalidAnswerError, InvalidSourceInputError
from backend.domain.ports.format_reader import FormatReader
from backend.domain.value_objects.content import LocalVideo, SubtitlesContent
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.question import Question, QuestionOption
from backend.domain.value_objects.source_input import LocalFile
from backend.infrastructure.adapters.regex_srt_parser import RegexSrtParser
from backend.infrastructure.readers.subtitles import subtitles_document

if TYPE_CHECKING:
    from backend.domain.ports.audio_track_lister import AudioTrackLister
    from backend.domain.ports.file_reader import FileReader
    from backend.domain.ports.subtitle_extractor import SubtitleExtractor
    from backend.domain.value_objects.audio_track_info import AudioTrackInfo
    from backend.domain.value_objects.content import Content
    from backend.domain.value_objects.question import Answers
    from backend.domain.value_objects.source_input import SourceInput
    from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo

logger = logging.getLogger(__name__)

SUBTITLE_TRACK_QUESTION_ID = "video.subtitle_track"
AUDIO_TRACK_QUESTION_ID = "video.audio_track"
NO_SUBTITLES_MESSAGE = "No subtitles found in video. Please attach a .srt file."
EMPTY_SRT_MESSAGE = "Attached .srt file is empty."


class VideoFileReader(FormatReader):
    """A video with its own or an attached .srt; asks which tracks to take if it has several."""

    def __init__(
        self,
        file_reader: FileReader,
        subtitle_extractor: SubtitleExtractor,
        audio_track_lister: AudioTrackLister,
    ) -> None:
        self._file_reader = file_reader
        self._subtitle_extractor = subtitle_extractor
        self._audio_track_lister = audio_track_lister
        self._parser = RegexSrtParser()

    @property
    def format(self) -> Format:
        return Format.VIDEO_FILE

    def questions(self, source_input: SourceInput) -> tuple[Question, ...]:
        video = _video(source_input)
        questions: list[Question] = []
        if video.subtitles_path is None:
            subtitle_tracks = self._subtitle_tracks(video.path)
            if len(subtitle_tracks) > 1:
                questions.append(_track_question(
                    SUBTITLE_TRACK_QUESTION_ID, "Subtitle track",
                    [_subtitle_option(track) for track in subtitle_tracks],
                ))
        audio_tracks = self._audio_tracks(video.path)
        if len(audio_tracks) > 1:
            questions.append(_track_question(
                AUDIO_TRACK_QUESTION_ID, "Audio track",
                [_audio_option(track) for track in audio_tracks],
            ))
        return tuple(questions)

    def read(self, source_input: SourceInput, answers: Answers) -> Content:
        video = _video(source_input)
        srt_text = self._srt_text(video, answers)
        audio_tracks = self._audio_tracks(video.path)
        audio_track = (
            _track_index(answers, AUDIO_TRACK_QUESTION_ID) if len(audio_tracks) > 1 else None
        )
        return SubtitlesContent(
            title=video.path.rsplit("/", 1)[-1],
            document=subtitles_document(srt_text, self._parser),
            video=LocalVideo(path=video.path, audio_track=audio_track),
        )

    def _srt_text(self, video: LocalFile, answers: Answers) -> str:
        if video.subtitles_path is not None:
            srt_text = self._file_reader.read_text(video.subtitles_path)
            if not srt_text.strip():
                raise InvalidSourceInputError(EMPTY_SRT_MESSAGE)
            return srt_text
        tracks = self._subtitle_tracks(video.path)
        index = (
            tracks[0].index
            if len(tracks) == 1
            else _track_index(answers, SUBTITLE_TRACK_QUESTION_ID)
        )
        return self._subtitle_extractor.extract(video.path, index)

    def _subtitle_tracks(self, path: str) -> list[SubtitleTrackInfo]:
        tracks = self._subtitle_extractor.list_tracks(path)
        logger.info("Video %s: found %d subtitle track(s)", path, len(tracks))
        if not tracks:
            raise InvalidSourceInputError(NO_SUBTITLES_MESSAGE)
        return tracks

    def _audio_tracks(self, path: str) -> list[AudioTrackInfo]:
        tracks = self._audio_track_lister.list_audio_tracks(path)
        logger.info("Video %s: found %d audio track(s)", path, len(tracks))
        return tracks


def _video(source_input: SourceInput) -> LocalFile:
    if not isinstance(source_input, LocalFile):
        msg = "A video is read from a file"
        raise InvalidSourceInputError(msg)
    return source_input


def _track_question(question_id: str, prompt: str, options: list[QuestionOption]) -> Question:
    return Question(id=question_id, prompt=prompt, options=tuple(options), default=options[0].id)


def _track_index(answers: Answers, question_id: str) -> int:
    answer = answers.get(question_id)
    if answer is None or not answer.isdigit():
        msg = f"No track chosen for {question_id}"
        raise InvalidAnswerError(msg)
    return int(answer)


def _subtitle_option(track: SubtitleTrackInfo) -> QuestionOption:
    return _track_option(track.index, track.title, track.language, track.codec, None)


def _audio_option(track: AudioTrackInfo) -> QuestionOption:
    return _track_option(track.index, track.title, track.language, track.codec, track.channels)


def _track_option(
    index: int, title: str | None, language: str | None, codec: str, channels: int | None,
) -> QuestionOption:
    name = title or language or f"Track {index}"
    shown_language = language if title and language else None
    facts = (shown_language, codec, f"{channels} channels" if channels else None)
    return QuestionOption(id=str(index), label=name, facts=tuple(f for f in facts if f))
