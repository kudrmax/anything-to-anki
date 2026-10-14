from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_status import SourceStatus

from tests.candidate_sorter_support import threshold_resolver
from tests.phrase_support import phrase
from tests.vocabulary_support import user_vocabulary

if TYPE_CHECKING:
    from backend.domain.entities.candidate_media import CandidateMedia


def _make_source(source_format: Format) -> Source:
    is_video = source_format is Format.VIDEO_FILE
    return Source(
        id=1,
        status=SourceStatus.PROCESSING,
        format=source_format,
        kind=Kind.SUBTITLES if is_video else Kind.TEXT,
        video_path="/tmp/movie.mp4" if is_video else None,
    )


def _make_candidate(fragment: str, position: DocumentPosition) -> StoredCandidate:
    return StoredCandidate(
        id=1, source_id=1, lemma="test", pos="NOUN",
        cefr_level="B1", zipf_frequency=3.5,
        source_phrase=phrase(fragment),
        occurrences=1, status=CandidateStatus.PENDING, phrase_position=position,
    )


def _paragraph(*lines: Line) -> Document:
    return Document((Paragraph(lines=lines, mode=ParagraphMode.FLOW),))


@pytest.mark.unit
class TestProcessVideoSource:
    def _make_use_case(
        self,
        source: Source,
        candidates: list[StoredCandidate],
        document: Document,
    ) -> ProcessSourceUseCase:
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = source
        candidate_repo = MagicMock()
        # create_batch returns candidates with IDs set
        returned = [replace(c, id=i + 1) for i, c in enumerate(candidates)]
        candidate_repo.create_batch.return_value = returned
        known_word_repo = MagicMock()
        known_word_repo.get_all_pairs.return_value = set()
        settings_repo = MagicMock()
        settings_repo.get.return_value = "B1"
        analyze_result = MagicMock()
        analyze_result.candidates = []
        analyze_result.text = "some text"
        analyze_text = MagicMock()
        analyze_text.execute.return_value = analyze_result
        document_repo = MagicMock()
        document_repo.get.return_value = document
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._media_repo = MagicMock()
        return ProcessSourceUseCase(
            source_repo=source_repo,
            candidate_repo=candidate_repo,
            vocabulary=user_vocabulary(known_word_repo),
            settings_repo=settings_repo,
            threshold_resolver=threshold_resolver(settings_repo),
            analyze_text_use_case=analyze_text,
            document_repo=document_repo,
            media_repo=self._media_repo,
        )

    def test_phrase_gets_the_time_of_the_lines_it_takes(self) -> None:
        document = _paragraph(
            Line("I think you should", 1200, 2500), Line("go back to school.", 2500, 4000),
        )
        source = _make_source(Format.VIDEO_FILE)
        candidate = _make_candidate("you should go back", DocumentPosition(0, 0, 8, 1, 7))
        uc = self._make_use_case(source, [candidate], document)
        uc.execute(source_id=1)

        # media_repo.upsert called with CandidateMedia having correct timecodes
        self._media_repo.upsert.assert_called_once()
        upserted: CandidateMedia = self._media_repo.upsert.call_args[0][0]
        assert upserted.start_ms == 1200
        assert upserted.end_ms == 4000
        assert upserted.screenshot_path is None
        assert upserted.audio_path is None

    def test_untimed_lines_give_no_time(self) -> None:
        source = _make_source(Format.PLAIN)
        candidate = _make_candidate("plain text", DocumentPosition(0, 0, 0, 0, 10))
        uc = self._make_use_case(source, [candidate], _paragraph(Line("plain text")))
        uc.execute(source_id=1)

        # No media rows created for non-video source
        self._media_repo.upsert.assert_not_called()
