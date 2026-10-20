from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.regenerate_phrase_media import RegeneratePhraseMediaUseCase
from backend.application.utils.requested_cards import RequestedCards
from backend.domain.exceptions import (
    PhraseChangedError,
    PhraseNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.adapters.local_media_files import LocalMediaFiles

from tests.phrase_support import make_occurrence

if TYPE_CHECKING:
    from backend.domain.entities.candidate_media import CandidateMedia


HOW_ARE_YOU = DocumentPosition(block=0, start_line=1, start_char=0, end_line=1, end_char=12)
SOURCE_ID = 42
WORD_ID = 10
PHRASE_ID = 17


def _document() -> Document:
    return Document((
        Paragraph(
            lines=(Line("Hello world.", 1000, 2000), Line("How are you?", 3000, 4000)),
            mode=ParagraphMode.FLOW,
        ),
    ))


class _Setup:
    def __init__(
        self,
        tmp_path: Path,
        *,
        position: DocumentPosition | None = HOW_ARE_YOU,
        has_video: bool = True,
        video_exists: bool = True,
        audio_track_index: int | None = None,
        phrase_found: bool = True,
        busy_with: SourceOperationKind | None = None,
        holds: bool = True,
    ) -> None:
        video = tmp_path / "movie.mkv"
        if video_exists:
            video.write_bytes(b"video")
        self.media_root = tmp_path / "media"
        shown = replace(
            make_occurrence("How are you?", candidate_id=WORD_ID),
            id=PHRASE_ID, phrase_position=position,
        )
        self.occurrence_repo = MagicMock()
        self.occurrence_repo.get.return_value = shown if phrase_found else None
        self.occurrence_repo.holds_revision.return_value = holds
        candidate_repo = MagicMock()
        candidate_repo.get_by_id.return_value = MagicMock(id=WORD_ID, source_id=SOURCE_ID)
        lock = MagicMock()
        lock.held.return_value = busy_with
        source = MagicMock(
            id=SOURCE_ID, has_video=has_video, video_path=str(video),
            audio_track_index=audio_track_index,
        )
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source
        document_repo = MagicMock()
        document_repo.get.return_value = _document()
        resolver = MagicMock()
        resolver.resolve.side_effect = lambda path, _method: path
        self.extractor = MagicMock()
        self.extractor.extract_screenshot.side_effect = (
            lambda _video, _ms, path: Path(path).write_bytes(b"new frame")
        )
        self.extractor.extract_audio.side_effect = (
            lambda _video, _start, _end, path, audio_track_index:
            Path(path).write_bytes(b"new clip")
        )
        self.media_repo = MagicMock()
        self.use_case = RegeneratePhraseMediaUseCase(
            cards=RequestedCards(candidate_repo, self.occurrence_repo, lock),
            occurrence_repo=self.occurrence_repo,
            media_repo=self.media_repo,
            source_repo=source_repo,
            document_repo=document_repo,
            media_extractor=self.extractor,
            media_files=LocalMediaFiles(str(self.media_root)),
            video_path_resolver=resolver,
        )
        self.video = str(video)

    def files(self) -> dict[str, bytes]:
        folder = self.media_root / str(SOURCE_ID)
        return {p.name: p.read_bytes() for p in folder.iterdir()} if folder.exists() else {}


@pytest.mark.unit
class TestRegeneratePhraseMedia:
    def test_takes_the_time_of_the_lines_the_phrase_takes(self, tmp_path: Path) -> None:
        setup = _Setup(tmp_path)

        setup.use_case.execute(PHRASE_ID)

        folder = setup.media_root / str(SOURCE_ID)
        screenshot = setup.extractor.extract_screenshot.call_args
        assert screenshot.args[:2] == (setup.video, 3500)
        audio = setup.extractor.extract_audio.call_args
        assert audio.args[:3] == (setup.video, 3000, 4000)
        assert audio.kwargs == {"audio_track_index": None}
        phrase_id, upserted = setup.media_repo.upsert_for_phrase.call_args.args
        media: CandidateMedia = upserted
        assert phrase_id == PHRASE_ID
        assert (media.candidate_id, media.start_ms, media.end_ms) == (WORD_ID, 3000, 4000)
        assert media.screenshot_path == str(folder / f"p{PHRASE_ID}_screenshot.webp")
        assert media.audio_path == str(folder / f"p{PHRASE_ID}_audio.m4a")
        assert setup.files() == {
            f"p{PHRASE_ID}_screenshot.webp": b"new frame", f"p{PHRASE_ID}_audio.m4a": b"new clip",
        }

    def test_uses_source_audio_track_index(self, tmp_path: Path) -> None:
        setup = _Setup(tmp_path, audio_track_index=2)

        setup.use_case.execute(PHRASE_ID)

        assert setup.extractor.extract_audio.call_args.kwargs == {"audio_track_index": 2}

    def test_new_frame_leaves_the_meaning_image_alone(self, tmp_path: Path) -> None:
        picked = tmp_path / "media" / str(SOURCE_ID) / f"{WORD_ID}_meaning.abc123.webp"
        picked.parent.mkdir(parents=True)
        picked.write_bytes(b"picture")

        _Setup(tmp_path).use_case.execute(PHRASE_ID)

        assert picked.read_bytes() == b"picture"

    def test_raises_if_phrase_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(PhraseNotFoundError):
            _Setup(tmp_path, phrase_found=False).use_case.execute(PHRASE_ID)

    def test_raises_if_source_not_video(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not a video"):
            _Setup(tmp_path, has_video=False).use_case.execute(PHRASE_ID)

    def test_raises_if_video_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Video file missing"):
            _Setup(tmp_path, video_exists=False).use_case.execute(PHRASE_ID)

    def test_raises_if_phrase_has_no_place_in_the_document(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Fragment not found"):
            _Setup(tmp_path, position=None).use_case.execute(PHRASE_ID)

    def test_is_refused_while_the_source_is_rebuilt(self, tmp_path: Path) -> None:
        setup = _Setup(tmp_path, busy_with=SourceOperationKind.UPDATE)

        with pytest.raises(SourceOperationBusyError):
            setup.use_case.execute(PHRASE_ID)
        setup.extractor.extract_screenshot.assert_not_called()

    def test_a_phrase_changed_meanwhile_keeps_its_media(self, tmp_path: Path) -> None:
        setup = _Setup(tmp_path, holds=False)
        folder = setup.media_root / str(SOURCE_ID)
        folder.mkdir(parents=True)
        (folder / f"p{PHRASE_ID}_screenshot.webp").write_bytes(b"fresh")

        with pytest.raises(PhraseChangedError):
            setup.use_case.execute(PHRASE_ID)
        setup.media_repo.upsert_for_phrase.assert_not_called()
        assert setup.files() == {f"p{PHRASE_ID}_screenshot.webp": b"fresh"}
