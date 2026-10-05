from datetime import UTC, datetime

import pytest
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.export_readiness import export_group, missing_parts
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.export_group import ExportGroup
from backend.domain.value_objects.missing_card_part import MissingCardPart

_NOW = datetime(2026, 10, 5, tzinfo=UTC)


def _candidate(
    meaning: str | None = None,
    clip_path: str | None = None,
    tts_path: str | None = None,
) -> StoredCandidate:
    return StoredCandidate(
        id=1,
        source_id=1,
        lemma="tense",
        pos="ADJ",
        cefr_level="B2",
        zipf_frequency=3.5,
        context_fragment="Gordon was tense",
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.LEARN,
        meaning=CandidateMeaning(
            candidate_id=1, meaning=meaning, translation=None, synonyms=None,
            examples=None, ipa=None, generated_at=_NOW,
        ),
        media=CandidateMedia(
            candidate_id=1, screenshot_path=None, audio_path=clip_path,
            start_ms=None, end_ms=None, generated_at=_NOW,
        ),
        tts=CandidateTTS(candidate_id=1, audio_path=tts_path, generated_at=_NOW),
    )


@pytest.mark.unit
class TestExportReadiness:
    def test_meaning_and_tts_is_ready(self) -> None:
        candidate = _candidate(meaning="stiff with nerves", tts_path="/a/tts.mp3")
        assert missing_parts(candidate) == []
        assert export_group(candidate) == ExportGroup.READY

    def test_video_clip_counts_as_audio(self) -> None:
        candidate = _candidate(meaning="stiff with nerves", clip_path="/a/clip.mp3")
        assert export_group(candidate) == ExportGroup.READY

    def test_no_meaning_is_incomplete(self) -> None:
        candidate = _candidate(tts_path="/a/tts.mp3")
        assert missing_parts(candidate) == [MissingCardPart.MEANING]
        assert export_group(candidate) == ExportGroup.INCOMPLETE

    def test_no_audio_is_incomplete(self) -> None:
        candidate = _candidate(meaning="stiff with nerves")
        assert missing_parts(candidate) == [MissingCardPart.AUDIO]

    def test_bare_candidate_misses_both(self) -> None:
        candidate = StoredCandidate(
            source_id=1, lemma="tense", pos="ADJ", cefr_level=None, zipf_frequency=3.5,
            context_fragment="Gordon was tense", fragment_purity="clean", occurrences=1,
            status=CandidateStatus.LEARN,
        )
        assert missing_parts(candidate) == [MissingCardPart.MEANING, MissingCardPart.AUDIO]
