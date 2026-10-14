from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.run_media_extraction_job import MediaExtractionUseCase
from backend.application.utils.generation_targets import GenerationCard
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    BadVideoFormatError,
    InvalidTimecodesError,
    PermanentMediaError,
)
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.phrase_ref import PhraseRef

from tests.phrase_support import make_occurrence, phrase

if TYPE_CHECKING:
    from pathlib import Path

WORD_ID = 10
PHRASE_ID = 17
REF = PhraseRef(PHRASE_ID, 0)


def _media(start_ms: int | None = 1000, end_ms: int | None = 2000) -> CandidateMedia:
    return CandidateMedia(
        candidate_id=WORD_ID, screenshot_path=None, audio_path=None,
        start_ms=start_ms, end_ms=end_ms, generated_at=None,
    )


def _card(media: CandidateMedia | None) -> GenerationCard:
    word = StoredCandidate(
        id=WORD_ID, source_id=1, lemma="test", pos="NOUN",
        cefr_level="B1", zipf_frequency=3.5,
        source_phrase=phrase("hello world"), occurrences=1,
        status=CandidateStatus.LEARN,
    )
    shown = replace(make_occurrence("hello world", candidate_id=WORD_ID), id=PHRASE_ID)
    return GenerationCard(word, replace(shown, media=media))


def _video(tmp_path: Path) -> str:
    video = tmp_path / "movie.mp4"
    video.write_bytes(b"video")
    return str(video)


def _make_source(video_path: str | None) -> MagicMock:
    source = MagicMock()
    source.id = 1
    source.video_path = video_path
    source.audio_track_index = 0
    return source


@pytest.mark.unit
class TestMediaExtractionUseCase:
    def _make_uc(
        self,
        tmp_path: Path,
        card: GenerationCard | None = None,
        source: MagicMock | None = None,
        holds: bool = True,
    ) -> tuple[MediaExtractionUseCase, MagicMock, MagicMock]:
        job_phrases = MagicMock()
        job_phrases.card.return_value = card
        job_phrases.holds.return_value = holds
        media_repo = MagicMock()
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source
        media_extractor = MagicMock()
        video_path_resolver = MagicMock()
        video_path_resolver.resolve.side_effect = lambda path, _method: path

        uc = MediaExtractionUseCase(
            job_phrases=job_phrases,
            media_repo=media_repo,
            source_repo=source_repo,
            media_extractor=media_extractor,
            media_root=str(tmp_path / "media"),
            video_path_resolver=video_path_resolver,
        )
        return uc, media_repo, media_extractor

    def test_execute_one_success(self, tmp_path: Path) -> None:
        video = _video(tmp_path)
        uc, media_repo, media_extractor = self._make_uc(
            tmp_path, _card(_media()), _make_source(video),
        )

        uc.execute_one(REF)

        screenshot = str(tmp_path / "media" / "1" / f"p{PHRASE_ID}_screenshot.webp")
        audio = str(tmp_path / "media" / "1" / f"p{PHRASE_ID}_audio.m4a")
        media_extractor.extract_screenshot.assert_called_once_with(
            video, 1500, screenshot,
        )
        media_extractor.extract_audio.assert_called_once_with(
            video, 1000, 2000, audio, audio_track_index=0,
        )
        phrase_id, upserted = media_repo.upsert_for_phrase.call_args.args
        assert phrase_id == PHRASE_ID
        assert upserted.candidate_id == WORD_ID
        assert (upserted.screenshot_path, upserted.audio_path) == (screenshot, audio)
        assert (upserted.start_ms, upserted.end_ms) == (1000, 2000)

    def test_a_phrase_gone_or_changed_before_the_job_gets_nothing(self, tmp_path: Path) -> None:
        uc, media_repo, media_extractor = self._make_uc(tmp_path, card=None)

        uc.execute_one(REF)

        media_extractor.extract_screenshot.assert_not_called()
        media_repo.upsert_for_phrase.assert_not_called()

    def test_a_phrase_changed_while_cutting_keeps_its_media(self, tmp_path: Path) -> None:
        uc, media_repo, _ = self._make_uc(
            tmp_path, _card(_media()), _make_source(_video(tmp_path)), holds=False,
        )

        uc.execute_one(REF)

        media_repo.upsert_for_phrase.assert_not_called()

    def test_execute_one_raises_invalid_timecodes(self, tmp_path: Path) -> None:
        uc, _, _ = self._make_uc(tmp_path, _card(None))

        with pytest.raises(InvalidTimecodesError):
            uc.execute_one(REF)

    def test_execute_one_raises_invalid_timecodes_when_start_ms_none(
        self, tmp_path: Path,
    ) -> None:
        uc, _, _ = self._make_uc(tmp_path, _card(_media(start_ms=None)))

        with pytest.raises(InvalidTimecodesError):
            uc.execute_one(REF)

    def test_execute_one_raises_bad_video_format_when_source_missing(
        self, tmp_path: Path,
    ) -> None:
        uc, _, _ = self._make_uc(tmp_path, _card(_media()), _make_source(None))

        with pytest.raises(BadVideoFormatError):
            uc.execute_one(REF)

    def test_execute_one_raises_bad_video_format_when_file_missing(
        self, tmp_path: Path,
    ) -> None:
        uc, _, _ = self._make_uc(
            tmp_path, _card(_media()), _make_source("/nonexistent/path/movie.mp4"),
        )

        with pytest.raises(BadVideoFormatError):
            uc.execute_one(REF)

    def test_execute_one_raises_permanent_when_source_not_found(self, tmp_path: Path) -> None:
        uc, _, _ = self._make_uc(tmp_path, _card(_media()), source=None)

        with pytest.raises(PermanentMediaError, match="Source .* not found"):
            uc.execute_one(REF)

    def test_execute_one_propagates_extractor_error(self, tmp_path: Path) -> None:
        uc, _, media_extractor = self._make_uc(
            tmp_path, _card(_media()), _make_source(_video(tmp_path)),
        )
        media_extractor.extract_screenshot.side_effect = OSError("ffmpeg crashed")

        with pytest.raises(OSError, match="ffmpeg crashed"):
            uc.execute_one(REF)
