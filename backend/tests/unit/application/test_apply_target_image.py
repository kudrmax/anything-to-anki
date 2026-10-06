from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.apply_target_image import ApplyTargetImageUseCase
from backend.application.utils.meaning_image_placer import MeaningImagePlacer
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import UnknownImageUrlError
from backend.domain.ports.card_picture_encoder import CardPictureEncoder
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


def _candidate(
    pos: str = "NOUN",
    media: CandidateMedia | None = None,
    meaning_image: CandidateMeaningImage | None = None,
) -> StoredCandidate:
    return StoredCandidate(
        id=CANDIDATE_ID, source_id=SOURCE_ID, lemma="ladder", pos=pos, cefr_level="B1",
        zipf_frequency=3.5, context_fragment="climb the ladder", fragment_purity="clean",
        occurrences=1, status=CandidateStatus.PENDING, media=media, meaning_image=meaning_image,
    )


class _WritingDownloader(FileDownloader):
    def __init__(self) -> None:
        self.urls: list[str] = []

    def download(self, url: str, dest: str) -> None:
        self.urls.append(url)
        with open(dest, "wb") as out:
            out.write(b"picture")


class _CopyingEncoder(CardPictureEncoder):
    def __init__(self) -> None:
        self.pictures: list[bytes] = []

    def encode(self, picture: bytes, out_path: str) -> None:
        self.pictures.append(picture)
        with open(out_path, "wb") as out:
            out.write(b"encoded")


class _Fixture:
    def __init__(self, tmp_path: Path, candidate: StoredCandidate) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = candidate
        self.image_repo = MagicMock()
        self.downloader = _WritingDownloader()
        self.encoder = _CopyingEncoder()
        source = MagicMock(spec=TargetImageSource)
        source.owns.side_effect = lambda url: url in (BING_URL, WIKI_URL)
        self.media_root = str(tmp_path)
        self.use_case = ApplyTargetImageUseCase(
            candidate_repo=repo,
            image_sources=[source],
            file_downloader=self.downloader,
            picture_placer=MeaningImagePlacer(
                image_repo=self.image_repo,
                picture_encoder=self.encoder,
                media_root=self.media_root,
            ),
        )

    def saved_image(self) -> CandidateMeaningImage:
        saved: CandidateMeaningImage = self.image_repo.upsert.call_args.args[0]
        return saved


class TestApplyTargetImage:
    def test_downloads_the_picture_and_makes_it_the_card_picture(self, tmp_path: Path) -> None:
        fx = _Fixture(tmp_path, _candidate())

        fx.use_case.execute(CANDIDATE_ID, BING_URL)

        saved = fx.saved_image()
        assert fx.downloader.urls == [BING_URL]
        assert saved.candidate_id == CANDIDATE_ID
        assert saved.image_path is not None
        expected_dir = os.path.join(fx.media_root, str(SOURCE_ID))
        assert os.path.dirname(saved.image_path) == expected_dir
        assert os.path.exists(saved.image_path)

    def test_shrinks_the_download_with_the_card_picture_encoder(self, tmp_path: Path) -> None:
        fx = _Fixture(tmp_path, _candidate())

        fx.use_case.execute(CANDIDATE_ID, WIKI_URL)

        saved_path = fx.saved_image().image_path or ""
        assert fx.encoder.pictures == [b"picture"]
        with open(saved_path, "rb") as saved:
            assert saved.read() == b"encoded"

    def test_file_name_keeps_the_screenshot_pattern_as_webp(self, tmp_path: Path) -> None:
        fx = _Fixture(tmp_path, _candidate())

        fx.use_case.execute(CANDIDATE_ID, WIKI_URL)

        name = os.path.basename(fx.saved_image().image_path or "")
        assert name.startswith(f"{CANDIDATE_ID}_meaning.")
        assert name.endswith(".webp")

    def test_keeps_only_the_encoded_file(self, tmp_path: Path) -> None:
        fx = _Fixture(tmp_path, _candidate())

        fx.use_case.execute(CANDIDATE_ID, BING_URL)

        saved_path = fx.saved_image().image_path or ""
        assert os.listdir(os.path.dirname(saved_path)) == [os.path.basename(saved_path)]

    def test_another_picture_gets_another_file_name(self, tmp_path: Path) -> None:
        first = _Fixture(tmp_path, _candidate())
        first.use_case.execute(CANDIDATE_ID, BING_URL)
        second = _Fixture(tmp_path, _candidate())
        second.use_case.execute(CANDIDATE_ID, WIKI_URL)

        assert first.saved_image().image_path != second.saved_image().image_path

    def test_leaves_the_video_frame_on_the_card(self, tmp_path: Path) -> None:
        frame = tmp_path / "frame.webp"
        frame.write_bytes(b"frame")
        media = CandidateMedia(
            candidate_id=CANDIDATE_ID, screenshot_path=str(frame), audio_path="/a/7_audio.m4a",
            start_ms=1000, end_ms=2000, generated_at=None,
        )
        fx = _Fixture(tmp_path, _candidate(media=media))

        fx.use_case.execute(CANDIDATE_ID, BING_URL)

        assert fx.saved_image().image_path != str(frame)
        assert frame.read_bytes() == b"frame"

    def test_replaces_the_previous_meaning_image(self, tmp_path: Path) -> None:
        previous = tmp_path / "7_meaning.old.webp"
        previous.write_bytes(b"old")
        image = CandidateMeaningImage(candidate_id=CANDIDATE_ID, image_path=str(previous))
        fx = _Fixture(tmp_path, _candidate(meaning_image=image))

        fx.use_case.execute(CANDIDATE_ID, BING_URL)

        assert fx.saved_image().image_path != str(previous)
        assert not previous.exists()

    def test_refuses_a_url_no_source_handed_out(self, tmp_path: Path) -> None:
        fx = _Fixture(tmp_path, _candidate())

        with pytest.raises(UnknownImageUrlError):
            fx.use_case.execute(CANDIDATE_ID, "https://evil.example/x.jpg")
        assert fx.downloader.urls == []
        fx.image_repo.upsert.assert_not_called()

    def test_any_part_of_speech_gets_a_picture(self, tmp_path: Path) -> None:
        fx = _Fixture(tmp_path, _candidate(pos="VERB"))

        fx.use_case.execute(CANDIDATE_ID, BING_URL)

        assert fx.downloader.urls == [BING_URL]
