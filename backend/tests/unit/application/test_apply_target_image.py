from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.apply_target_image import ApplyTargetImageUseCase
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import TargetImageNotSupportedError, UnknownImageUrlError
from backend.domain.ports.file_downloader import FileDownloader
from backend.domain.ports.target_image_source import TargetImageSource
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

CANDIDATE_ID = 7
SOURCE_ID = 3
BING_URL = "https://ts2.mm.bing.net/th?id=OIP.abc&pid=15.1"
WIKI_URL = "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Ladder.PNG/500px-Ladder.PNG"


def _candidate(pos: str = "NOUN", media: CandidateMedia | None = None) -> StoredCandidate:
    return StoredCandidate(
        id=CANDIDATE_ID, source_id=SOURCE_ID, lemma="ladder", pos=pos, cefr_level="B1",
        zipf_frequency=3.5, context_fragment="climb the ladder", fragment_purity="clean",
        occurrences=1, status=CandidateStatus.PENDING, media=media,
    )


class _WritingDownloader(FileDownloader):
    def __init__(self) -> None:
        self.urls: list[str] = []

    def download(self, url: str, dest: str) -> None:
        self.urls.append(url)
        with open(dest, "wb") as out:
            out.write(b"picture")


class _Fixture:
    def __init__(self, tmp_path: Path, candidate: StoredCandidate) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = candidate
        self.media_repo = MagicMock()
        self.downloader = _WritingDownloader()
        source = MagicMock(spec=TargetImageSource)
        source.owns.side_effect = lambda url: url in (BING_URL, WIKI_URL)
        self.media_root = str(tmp_path)
        self.use_case = ApplyTargetImageUseCase(
            candidate_repo=repo,
            media_repo=self.media_repo,
            image_sources=[source],
            file_downloader=self.downloader,
            media_root=self.media_root,
        )

    def saved_media(self) -> CandidateMedia:
        saved: CandidateMedia = self.media_repo.upsert.call_args.args[0]
        return saved


class TestApplyTargetImage:
    def test_downloads_the_picture_and_makes_it_the_card_picture(self, tmp_path: Path) -> None:
        fx = _Fixture(tmp_path, _candidate())

        fx.use_case.execute(CANDIDATE_ID, BING_URL)

        saved = fx.saved_media()
        assert fx.downloader.urls == [BING_URL]
        assert saved.candidate_id == CANDIDATE_ID
        assert saved.screenshot_path is not None
        expected_dir = os.path.join(fx.media_root, str(SOURCE_ID))
        assert os.path.dirname(saved.screenshot_path) == expected_dir
        assert os.path.exists(saved.screenshot_path)

    def test_file_name_keeps_the_screenshot_pattern_and_the_url_extension(
        self, tmp_path: Path,
    ) -> None:
        fx = _Fixture(tmp_path, _candidate())

        fx.use_case.execute(CANDIDATE_ID, WIKI_URL)

        name = os.path.basename(fx.saved_media().screenshot_path or "")
        assert name.startswith(f"{CANDIDATE_ID}_screenshot.")
        assert name.endswith(".png")

    def test_url_without_extension_is_saved_as_jpg(self, tmp_path: Path) -> None:
        fx = _Fixture(tmp_path, _candidate())

        fx.use_case.execute(CANDIDATE_ID, BING_URL)

        assert (fx.saved_media().screenshot_path or "").endswith(".jpg")

    def test_another_picture_gets_another_file_name(self, tmp_path: Path) -> None:
        first = _Fixture(tmp_path, _candidate())
        first.use_case.execute(CANDIDATE_ID, BING_URL)
        second = _Fixture(tmp_path, _candidate())
        second.use_case.execute(CANDIDATE_ID, WIKI_URL)

        assert first.saved_media().screenshot_path != second.saved_media().screenshot_path

    def test_replaces_the_video_frame_but_keeps_audio_and_timecodes(self, tmp_path: Path) -> None:
        frame = tmp_path / "frame.webp"
        frame.write_bytes(b"frame")
        media = CandidateMedia(
            candidate_id=CANDIDATE_ID, screenshot_path=str(frame), audio_path="/a/7_audio.m4a",
            start_ms=1000, end_ms=2000, generated_at=None,
        )
        fx = _Fixture(tmp_path, _candidate(media=media))

        fx.use_case.execute(CANDIDATE_ID, BING_URL)

        saved = fx.saved_media()
        assert saved.screenshot_path != str(frame)
        assert not frame.exists()
        assert (saved.audio_path, saved.start_ms, saved.end_ms) == ("/a/7_audio.m4a", 1000, 2000)

    def test_refuses_a_url_no_source_handed_out(self, tmp_path: Path) -> None:
        fx = _Fixture(tmp_path, _candidate())

        with pytest.raises(UnknownImageUrlError):
            fx.use_case.execute(CANDIDATE_ID, "https://evil.example/x.jpg")
        assert fx.downloader.urls == []
        fx.media_repo.upsert.assert_not_called()

    def test_refuses_a_target_that_is_not_a_noun(self, tmp_path: Path) -> None:
        fx = _Fixture(tmp_path, _candidate(pos="VERB"))

        with pytest.raises(TargetImageNotSupportedError):
            fx.use_case.execute(CANDIDATE_ID, BING_URL)
        assert fx.downloader.urls == []
