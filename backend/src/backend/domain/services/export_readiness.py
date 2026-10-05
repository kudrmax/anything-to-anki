from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.export_group import ExportGroup
from backend.domain.value_objects.missing_card_part import MissingCardPart

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate


def missing_parts(candidate: StoredCandidate) -> list[MissingCardPart]:
    """Required parts the card still lacks: a meaning and the phrase spoken."""
    missing: list[MissingCardPart] = []
    if candidate.meaning is None or not candidate.meaning.meaning:
        missing.append(MissingCardPart.MEANING)
    if not _has_phrase_audio(candidate):
        missing.append(MissingCardPart.AUDIO)
    return missing


def export_group(candidate: StoredCandidate) -> ExportGroup:
    return ExportGroup.INCOMPLETE if missing_parts(candidate) else ExportGroup.READY


def _has_phrase_audio(candidate: StoredCandidate) -> bool:
    has_clip = candidate.media is not None and bool(candidate.media.audio_path)
    has_tts = candidate.tts is not None and bool(candidate.tts.audio_path)
    return has_clip or has_tts
