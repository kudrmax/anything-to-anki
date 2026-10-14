from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from backend.application.use_cases.regenerate_candidate_media import (
    RegenerateCandidateMediaUseCase,
)
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.document_position import DocumentPosition

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from pathlib import Path

    from backend.domain.entities.candidate_media import CandidateMedia


HOW_ARE_YOU = DocumentPosition(block=0, start_line=1, start_char=0, end_line=1, end_char=12)


def _document() -> Document:
    return Document((
        Paragraph(
            lines=(Line("Hello world.", 1000, 2000), Line("How are you?", 3000, 4000)),
            mode=ParagraphMode.FLOW,
        ),
    ))


def _documents() -> MagicMock:
    document_repo = MagicMock()
    document_repo.get.return_value = _document()
    return document_repo


@pytest.mark.unit
class TestRegenerateCandidateMedia:
    def test_takes_the_time_of_the_lines_the_phrase_takes(self) -> None:
        candidate = MagicMock()
        candidate.id = 10
        candidate.source_id = 42
        candidate.source_phrase = phrase("How are you?")
        candidate.phrase_position = HOW_ARE_YOU
        candidate.media = None

        source = MagicMock()
        source.id = 42
        source.has_video = True
        source.video_path = "/videos/movie.mkv"
        source.audio_track_index = None

        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = candidate
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source
        media_extractor = MagicMock()
        media_repo = MagicMock()
        video_path_resolver = MagicMock()
        video_path_resolver.resolve.side_effect = lambda path, _method: path

        uc = RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=media_repo,
            source_repo=source_repo,
            document_repo=_documents(),
            media_extractor=media_extractor,
            media_root="/tmp/media",
            video_path_resolver=video_path_resolver,
        )

        base = "backend.application.use_cases.regenerate_candidate_media.os"
        with (
            patch(f"{base}.makedirs"),
            patch(f"{base}.path.exists", return_value=True),
        ):
            uc.execute(candidate_id=10)

        # Screenshot extracted at midpoint (3500 ms)
        screenshot_call = media_extractor.extract_screenshot.call_args
        assert screenshot_call.args[0] == "/videos/movie.mkv"
        assert screenshot_call.args[1] == 3500
        assert screenshot_call.args[2].endswith("10_screenshot.webp")

        # Audio extracted with new timecodes
        audio_call = media_extractor.extract_audio.call_args
        assert audio_call.args[0] == "/videos/movie.mkv"
        assert audio_call.args[1] == 3000
        assert audio_call.args[2] == 4000
        assert audio_call.args[3].endswith("10_audio.m4a")
        assert audio_call.kwargs.get("audio_track_index") is None

        # CandidateMedia upserted with correct fields
        media_repo.upsert.assert_called_once()
        upserted: CandidateMedia = media_repo.upsert.call_args[0][0]
        assert upserted.candidate_id == 10
        assert upserted.start_ms == 3000
        assert upserted.end_ms == 4000
        assert upserted.screenshot_path.endswith("10_screenshot.webp")
        assert upserted.audio_path.endswith("10_audio.m4a")

    def test_uses_source_audio_track_index(self) -> None:
        candidate = MagicMock()
        candidate.id = 10
        candidate.source_id = 42
        candidate.source_phrase = phrase("How are you?")
        candidate.phrase_position = HOW_ARE_YOU
        candidate.media = None

        source = MagicMock()
        source.id = 42
        source.has_video = True
        source.video_path = "/videos/movie.mkv"
        source.audio_track_index = 2

        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = candidate
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source
        media_extractor = MagicMock()
        media_repo = MagicMock()
        video_path_resolver = MagicMock()
        video_path_resolver.resolve.side_effect = lambda path, _method: path

        uc = RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=media_repo,
            source_repo=source_repo,
            document_repo=_documents(),
            media_extractor=media_extractor,
            media_root="/tmp/media",
            video_path_resolver=video_path_resolver,
        )

        base = "backend.application.use_cases.regenerate_candidate_media.os"
        with (
            patch(f"{base}.makedirs"),
            patch(f"{base}.path.exists", return_value=True),
        ):
            uc.execute(candidate_id=10)

        audio_call = media_extractor.extract_audio.call_args
        assert audio_call.kwargs.get("audio_track_index") == 2

    def test_new_frame_leaves_the_meaning_image_alone(self, tmp_path: Path) -> None:
        video = tmp_path / "movie.mkv"
        video.write_bytes(b"video")
        picked = tmp_path / "42" / "10_meaning.abc123.webp"
        picked.parent.mkdir()
        picked.write_bytes(b"picture")

        candidate = MagicMock()
        candidate.id = 10
        candidate.source_id = 42
        candidate.source_phrase = phrase("How are you?")
        candidate.phrase_position = HOW_ARE_YOU
        candidate.media = None
        candidate.meaning_image = CandidateMeaningImage(candidate_id=10, image_path=str(picked))
        source = MagicMock()
        source.id = 42
        source.has_video = True
        source.video_path = str(video)
        source.audio_track_index = None
        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = candidate
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source
        video_path_resolver = MagicMock()
        video_path_resolver.resolve.side_effect = lambda path, _method: path

        RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=MagicMock(),
            source_repo=source_repo,
            document_repo=_documents(),
            media_extractor=MagicMock(),
            media_root=str(tmp_path),
            video_path_resolver=video_path_resolver,
        ).execute(candidate_id=10)

        assert picked.read_bytes() == b"picture"

    def test_raises_if_candidate_not_found(self) -> None:
        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = None

        uc = RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=MagicMock(),
            source_repo=MagicMock(),
            document_repo=_documents(),
            media_extractor=MagicMock(),
            media_root="/tmp/media",
            video_path_resolver=MagicMock(),
        )

        with pytest.raises(ValueError, match="not found"):
            uc.execute(candidate_id=999)

    def test_raises_if_source_not_video(self) -> None:
        candidate = MagicMock()
        candidate.id = 10
        candidate.source_id = 42
        source = MagicMock()
        source.has_video = False

        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = candidate
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source

        uc = RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=MagicMock(),
            source_repo=source_repo,
            document_repo=_documents(),
            media_extractor=MagicMock(),
            media_root="/tmp/media",
            video_path_resolver=MagicMock(),
        )

        with pytest.raises(ValueError, match="not a video"):
            uc.execute(candidate_id=10)

    def test_raises_if_video_file_missing(self) -> None:
        candidate = MagicMock()
        candidate.id = 10
        candidate.source_id = 42
        source = MagicMock()
        source.id = 42
        source.has_video = True
        source.video_path = "/videos/missing.mkv"

        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = candidate
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source

        video_path_resolver = MagicMock()
        video_path_resolver.resolve.side_effect = lambda path, _method: path

        uc = RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=MagicMock(),
            source_repo=source_repo,
            document_repo=_documents(),
            media_extractor=MagicMock(),
            media_root="/tmp/media",
            video_path_resolver=video_path_resolver,
        )

        exists_path = "backend.application.use_cases.regenerate_candidate_media.os.path.exists"
        with (
            patch(exists_path, return_value=False),
            pytest.raises(ValueError, match="Video file missing"),
        ):
            uc.execute(candidate_id=10)

    def test_raises_if_phrase_has_no_place_in_the_document(self) -> None:
        candidate = MagicMock()
        candidate.id = 10
        candidate.source_id = 42
        candidate.source_phrase = phrase("This text is not in SRT at all.")
        candidate.phrase_position = None

        source = MagicMock()
        source.id = 42
        source.has_video = True
        source.video_path = "/videos/movie.mkv"
        source.audio_track_index = None

        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = candidate
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source

        video_path_resolver = MagicMock()
        video_path_resolver.resolve.side_effect = lambda path, _method: path

        uc = RegenerateCandidateMediaUseCase(
            candidate_repo=candidate_repo,
            media_repo=MagicMock(),
            source_repo=source_repo,
            document_repo=_documents(),
            media_extractor=MagicMock(),
            media_root="/tmp/media",
            video_path_resolver=video_path_resolver,
        )

        exists_path = "backend.application.use_cases.regenerate_candidate_media.os.path.exists"
        with (
            patch(exists_path, return_value=True),
            pytest.raises(ValueError, match="Fragment not found"),
        ):
            uc.execute(candidate_id=10)
