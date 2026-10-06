from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.paste_target_image import PasteTargetImageUseCase
from backend.application.utils.meaning_image_placer import MeaningImagePlacer
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.ports.card_picture_encoder import CardPictureEncoder
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

CANDIDATE_ID = 7
SOURCE_ID = 3
PICTURE = b"pasted picture"
NOT_A_PICTURE = b"plain text"


def _candidate(
    media: CandidateMedia | None = None,
    meaning_image: CandidateMeaningImage | None = None,
) -> StoredCandidate:
    return StoredCandidate(
        id=CANDIDATE_ID, source_id=SOURCE_ID, lemma="ladder", pos="NOUN", cefr_level="B1",
        zipf_frequency=3.5, context_fragment="climb the ladder", fragment_purity="clean",
        occurrences=1, status=CandidateStatus.PENDING, media=media, meaning_image=meaning_image,
    )


class _CopyingEncoder(CardPictureEncoder):
    def __init__(self) -> None:
        self.pictures: list[bytes] = []

    def encode(self, picture: bytes, out_path: str) -> None:
        if picture == NOT_A_PICTURE:
            raise OSError("cannot identify image file")
        self.pictures.append(picture)
        with open(out_path, "wb") as out:
            out.write(b"encoded")


class _Fixture:
    def __init__(self, tmp_path: Path, candidate: StoredCandidate | None) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = candidate
        self.image_repo = MagicMock()
        self.encoder = _CopyingEncoder()
        self.media_root = str(tmp_path)
        self.use_case = PasteTargetImageUseCase(
            candidate_repo=repo,
            picture_placer=MeaningImagePlacer(
                image_repo=self.image_repo,
                picture_encoder=self.encoder,
                media_root=self.media_root,
            ),
        )

    def saved_image(self) -> CandidateMeaningImage:
        saved: CandidateMeaningImage = self.image_repo.upsert.call_args.args[0]
        return saved


class TestPasteTargetImage:
    def test_shrinks_the_pasted_picture_with_the_card_encoder(self, tmp_path: Path) -> None:
        fx = _Fixture(tmp_path, _candidate())

        fx.use_case.execute(CANDIDATE_ID, PICTURE)

        saved_path = fx.saved_image().image_path or ""
        assert fx.encoder.pictures == [PICTURE]
        assert os.path.dirname(saved_path) == os.path.join(fx.media_root, str(SOURCE_ID))
        assert os.path.basename(saved_path).startswith(f"{CANDIDATE_ID}_meaning.")
        assert saved_path.endswith(".webp")
        with open(saved_path, "rb") as saved:
            assert saved.read() == b"encoded"

    def test_leaves_the_video_frame_on_the_card(self, tmp_path: Path) -> None:
        frame = tmp_path / "frame.webp"
        frame.write_bytes(b"frame")
        media = CandidateMedia(
            candidate_id=CANDIDATE_ID, screenshot_path=str(frame), audio_path="/a/7_audio.m4a",
            start_ms=1000, end_ms=2000, generated_at=None,
        )
        fx = _Fixture(tmp_path, _candidate(media=media))

        fx.use_case.execute(CANDIDATE_ID, PICTURE)

        assert fx.saved_image().image_path != str(frame)
        assert frame.read_bytes() == b"frame"

    def test_another_picture_gets_another_file_name(self, tmp_path: Path) -> None:
        first = _Fixture(tmp_path, _candidate())
        first.use_case.execute(CANDIDATE_ID, PICTURE)
        second = _Fixture(tmp_path, _candidate())
        second.use_case.execute(CANDIDATE_ID, b"another picture")

        assert first.saved_image().image_path != second.saved_image().image_path

    def test_bytes_that_are_not_a_picture_leave_the_card_as_it_was(self, tmp_path: Path) -> None:
        previous = tmp_path / "7_meaning.old.webp"
        previous.write_bytes(b"old")
        image = CandidateMeaningImage(candidate_id=CANDIDATE_ID, image_path=str(previous))
        fx = _Fixture(tmp_path, _candidate(meaning_image=image))

        with pytest.raises(OSError):
            fx.use_case.execute(CANDIDATE_ID, NOT_A_PICTURE)
        assert previous.exists()
        fx.image_repo.upsert.assert_not_called()

    def test_unknown_candidate(self, tmp_path: Path) -> None:
        fx = _Fixture(tmp_path, None)

        with pytest.raises(CandidateNotFoundError):
            fx.use_case.execute(CANDIDATE_ID, PICTURE)
