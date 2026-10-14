"""Readiness for Anki, by the phrase of the decision."""
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.occurrence import Occurrence
from backend.domain.services.export_readiness import export_group, missing_parts
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.export_group import ExportGroup
from backend.domain.value_objects.missing_card_part import MissingCardPart
from backend.domain.value_objects.phrase_origin_kind import DecisionKind, OccurrenceOrigin

from tests.phrase_support import phrase

_NOW = datetime(2026, 10, 5, tzinfo=UTC)
TEXT = "Gordon was tense"


def _decision(
    meaning: str | None = None,
    clip_path: str | None = None,
    tts_path: str | None = None,
    kind: DecisionKind = DecisionKind.LEARN,
) -> Occurrence:
    return Occurrence(
        id=1, candidate_id=1, origin=OccurrenceOrigin.AUTO,
        source_phrase=phrase(TEXT, "tense"), phrase_position=None, key=None,
        fragment_score=None, is_decision=True, decision_kind=kind,
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
        card = _decision(meaning="stiff with nerves", tts_path="/a/tts.mp3")
        assert missing_parts(card) == []
        assert export_group(card) == ExportGroup.READY

    def test_video_clip_counts_as_audio(self) -> None:
        card = _decision(meaning="stiff with nerves", clip_path="/a/clip.mp3")
        assert export_group(card) == ExportGroup.READY

    def test_no_meaning_is_incomplete(self) -> None:
        card = _decision(tts_path="/a/tts.mp3")
        assert missing_parts(card) == [MissingCardPart.MEANING]
        assert export_group(card) == ExportGroup.INCOMPLETE

    def test_no_audio_is_incomplete(self) -> None:
        card = _decision(meaning="stiff with nerves")
        assert missing_parts(card) == [MissingCardPart.AUDIO]

    def test_bare_phrase_misses_both(self) -> None:
        card = replace(_decision(), meaning=None, media=None, tts=None)
        assert missing_parts(card) == [MissingCardPart.MEANING, MissingCardPart.AUDIO]

    def test_a_cloze_decision_without_markup_is_incomplete(self) -> None:
        card = _decision(meaning="stiff", tts_path="/a/tts.mp3", kind=DecisionKind.CLOZE)
        assert missing_parts(card) == [MissingCardPart.CLOZE]
        assert export_group(card) == ExportGroup.INCOMPLETE

    def test_a_cloze_decision_with_markup_is_ready(self) -> None:
        card = replace(
            _decision(meaning="stiff", tts_path="/a/tts.mp3", kind=DecisionKind.CLOZE),
            cloze=CandidateCloze(1, (2,), ClozeHintKind.NONE, None, TEXT),
        )
        assert export_group(card) == ExportGroup.READY
