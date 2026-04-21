from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.parsed_srt import ParsedSrt
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.subtitle_block import SubtitleBlock

if TYPE_CHECKING:
    from backend.domain.entities.candidate_media import CandidateMedia


def _make_source(input_method: InputMethod, raw_text: str = "") -> Source:
    return Source(
        id=1,
        raw_text=raw_text,
        status=SourceStatus.PROCESSING,
        input_method=input_method,
        content_type=ContentType.VIDEO if input_method == InputMethod.VIDEO_FILE else ContentType.TEXT,
        video_path="/tmp/movie.mp4" if input_method == InputMethod.VIDEO_FILE else None,
    )


def _make_candidate(fragment: str) -> StoredCandidate:
    return StoredCandidate(
        id=1, source_id=1, lemma="test", pos="NOUN",
        cefr_level="B1", zipf_frequency=3.5,
        context_fragment=fragment, fragment_purity="clean",
        occurrences=1, status=CandidateStatus.PENDING,
    )


@pytest.mark.unit
class TestProcessVideoSource:
    def _make_use_case(
        self,
        source: Source,
        candidates: list[StoredCandidate],
    ) -> ProcessSourceUseCase:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source
        candidate_repo = MagicMock()
        # create_batch returns candidates with IDs set
        returned = [StoredCandidate(
            id=i + 1, source_id=c.source_id, lemma=c.lemma, pos=c.pos,
            cefr_level=c.cefr_level, zipf_frequency=c.zipf_frequency,
            context_fragment=c.context_fragment,
            fragment_purity=c.fragment_purity, occurrences=c.occurrences,
            status=c.status,
        ) for i, c in enumerate(candidates)]
        candidate_repo.create_batch.return_value = returned
        known_word_repo = MagicMock()
        known_word_repo.get_all_pairs.return_value = set()
        settings_repo = MagicMock()
        settings_repo.get.return_value = "B1"
        analyze_result = MagicMock()
        analyze_result.candidates = candidates
        analyze_result.cleaned_text = "some text"
        analyze_text = MagicMock()
        analyze_text.execute.return_value = analyze_result
        structured_parser = MagicMock()
        parsed_srt = ParsedSrt(
            text="I think you should\ngo back to school.",
            blocks=(
                SubtitleBlock(start_ms=1200, end_ms=2500, char_start=0, char_end=19),
                SubtitleBlock(start_ms=2500, end_ms=4000, char_start=19, char_end=38),
            ),
        )
        structured_parser.parse_structured.return_value = parsed_srt
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._media_repo = MagicMock()
        return ProcessSourceUseCase(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            known_word_repo=known_word_repo,
            settings_repo=settings_repo,
            analyze_text_use_case=analyze_text,
            structured_srt_parser=structured_parser,
            media_repo=self._media_repo,
        )

    def test_video_source_sets_timecodes_on_candidates(self) -> None:
        fragment = "you should\ngo back"  # spans both blocks
        source = _make_source(InputMethod.VIDEO_FILE, raw_text="")
        candidate = _make_candidate(fragment)
        uc = self._make_use_case(source, [candidate])
        uc.execute(source_id=1)

        # media_repo.upsert called with CandidateMedia having correct timecodes
        self._media_repo.upsert.assert_called_once()
        upserted: CandidateMedia = self._media_repo.upsert.call_args[0][0]
        assert upserted.start_ms == 1200
        assert upserted.end_ms == 4000
        assert upserted.screenshot_path is None
        assert upserted.audio_path is None

    def test_non_video_source_no_timecodes(self) -> None:
        source = _make_source(InputMethod.TEXT_PASTED, raw_text="plain text")
        candidate = _make_candidate("plain text")
        uc = self._make_use_case(source, [candidate])
        uc.execute(source_id=1)

        # No media rows created for non-video source
        self._media_repo.upsert.assert_not_called()
