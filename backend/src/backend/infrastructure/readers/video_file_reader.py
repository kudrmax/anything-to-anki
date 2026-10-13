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
                    [(track.index, _subtitle_label(track)) for track in subtitle_tracks],
                ))
        audio_tracks = self._audio_tracks(video.path)
        if len(audio_tracks) > 1:
            questions.append(_track_question(
                AUDIO_TRACK_QUESTION_ID, "Audio track",
                [(track.index, _audio_label(track)) for track in audio_tracks],
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


def _track_question(question_id: str, prompt: str, tracks: list[tuple[int, str]]) -> Question:
    return Question(
        id=question_id,
        prompt=prompt,
        options=tuple(QuestionOption(id=str(index), label=label) for index, label in tracks),
        default=str(tracks[0][0]),
    )


def _track_index(answers: Answers, question_id: str) -> int:
    answer = answers.get(question_id)
    if answer is None or not answer.isdigit():
        msg = f"No track chosen for {question_id}"
        raise InvalidAnswerError(msg)
    return int(answer)


def _subtitle_label(track: SubtitleTrackInfo) -> str:
    return _label(track.index, track.title, track.language, track.codec, None)


def _audio_label(track: AudioTrackInfo) -> str:
    return _label(track.index, track.title, track.language, track.codec, track.channels)


def _label(
    index: int, title: str | None, language: str | None, codec: str, channels: int | None,
) -> str:
    name = title or language or f"Track {index}"
    suffix = f" · {channels}ch" if channels else ""
    return f"{name} — {language or '—'} · {codec}{suffix}"
