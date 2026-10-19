from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.card_choice import is_cloze
from backend.domain.value_objects.export_group import ExportGroup
from backend.domain.value_objects.missing_card_part import MissingCardPart

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence


def missing_parts(decision: Occurrence) -> list[MissingCardPart]:
    """Required parts the card of a decision phrase still lacks: a meaning, the phrase
    spoken, and for a cloze the words it hides."""
    missing: list[MissingCardPart] = []
    if decision.meaning is None or not decision.meaning.meaning:
        missing.append(MissingCardPart.MEANING)
    if not _has_phrase_audio(decision):
        missing.append(MissingCardPart.AUDIO)
    if is_cloze(decision.card_state) and decision.cloze is None:
        missing.append(MissingCardPart.CLOZE)
    return missing


def export_group(decision: Occurrence) -> ExportGroup:
    return ExportGroup.INCOMPLETE if missing_parts(decision) else ExportGroup.READY


def _has_phrase_audio(decision: Occurrence) -> bool:
    has_clip = decision.media is not None and bool(decision.media.audio_path)
    has_tts = decision.tts is not None and bool(decision.tts.audio_path)
    return has_clip or has_tts
