from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from backend.application.utils.timecode_mapping import find_timecodes
from backend.domain.value_objects.source_type import SourceType

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.media_extractor import MediaExtractor
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.structured_srt_parser import StructuredSrtParser

logger = logging.getLogger(__name__)


class RegenerateCandidateMediaUseCase:
    """Regenerates screenshot and audio for a single candidate.

    Always recomputes timecodes from the current `context_fragment`,
    so this works correctly even after the user edits fragment boundaries.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
        structured_srt_parser: StructuredSrtParser,
        media_extractor: MediaExtractor,
        media_root: str,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._source_repo = source_repo
        self._parser = structured_srt_parser
        self._media_extractor = media_extractor
        self._media_root = media_root

    def execute(self, candidate_id: int) -> None:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate {candidate_id} not found")

        source = self._source_repo.get_by_id(candidate.source_id)
        if source is None:
            raise ValueError(f"Source {candidate.source_id} not found")
        if source.source_type != SourceType.VIDEO:
            raise ValueError(f"Source {source.id} is not a video")
        if source.video_path is None or not os.path.exists(source.video_path):
            raise ValueError(f"Video file missing for source {source.id}")

        # Parse SRT and recompute timecodes from current fragment
        parsed = self._parser.parse_structured(source.raw_text)
        timecodes = find_timecodes(candidate.context_fragment, parsed)
        if timecodes is None:
            raise ValueError("Fragment not found in subtitles")
        start_ms, end_ms = timecodes

        # Persist new timecodes
        self._candidate_repo.update_media_timecodes(candidate_id, start_ms=start_ms, end_ms=end_ms)

        # Prepare output paths
        out_dir = os.path.join(self._media_root, str(source.id))
        os.makedirs(out_dir, exist_ok=True)
        screenshot_path = os.path.join(out_dir, f"{candidate_id}_screenshot.webp")
        audio_path = os.path.join(out_dir, f"{candidate_id}_audio.m4a")

        # Extract both (overwrites existing files at same paths)
        midpoint_ms = (start_ms + end_ms) // 2
        self._media_extractor.extract_screenshot(source.video_path, midpoint_ms, screenshot_path)
        self._media_extractor.extract_audio(
            source.video_path,
            start_ms,
            end_ms,
            audio_path,
            audio_track_index=source.audio_track_index,
        )

        self._candidate_repo.update_media_paths(
            candidate_id,
            screenshot_path=screenshot_path,
            audio_path=audio_path,
        )

        logger.info(
            "Regenerated media for candidate %d: timecodes=(%d,%d) midpoint=%d",
            candidate_id, start_ms, end_ms, midpoint_ms,
        )
