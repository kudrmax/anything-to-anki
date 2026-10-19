from dataclasses import replace

import pytest
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.exceptions import InvalidEarnedSectionError
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.phrase_origin_kind import ShownBy

from tests.phrase_support import make_occurrence


def test_phrase_is_polished_unless_reverted() -> None:
    occ = make_occurrence(source_text="He glared.", polished_text="He looked angrily.")
    assert occ.phrase.text == "He looked angrily."
    assert replace(occ, polish_reverted=True).phrase.text == "He glared."


def test_phrase_is_source_without_polish() -> None:
    assert make_occurrence(source_text="He glared.").phrase.text == "He glared."


def test_has_results_counts_any_phrase_result() -> None:
    assert not make_occurrence().has_results
    assert make_occurrence(polished_text="x y z").has_results
    assert make_occurrence(meaning_text="angry look").has_results


def test_is_shown_when_someone_showed_it() -> None:
    assert not make_occurrence().is_shown
    assert make_occurrence(shown_by=ShownBy.SELECTION).is_shown
    assert make_occurrence(shown_by=ShownBy.USER).is_shown


def _media(screenshot: str | None, audio: str | None) -> CandidateMedia:
    return CandidateMedia(
        candidate_id=1, screenshot_path=screenshot, audio_path=audio,
        start_ms=None, end_ms=None, generated_at=None,
    )


def test_has_results_counts_media_screenshot() -> None:
    assert replace(make_occurrence(), media=_media("a.jpg", None)).has_results


def test_has_results_counts_clip_audio_alone() -> None:
    assert replace(make_occurrence(), media=_media(None, "a.m4a")).has_results


def test_has_results_ignores_empty_media() -> None:
    assert not replace(make_occurrence(), media=_media(None, None)).has_results


def test_has_results_counts_tts_audio() -> None:
    tts = CandidateTTS(candidate_id=1, audio_path="t.m4a", generated_at=None)
    assert replace(make_occurrence(), tts=tts).has_results


def test_has_results_counts_cloze() -> None:
    cloze = CandidateCloze(
        candidate_id=1, hidden_word_indices=(0,), hint_kind=next(iter(ClozeHintKind)),
        custom_hint=None, phrase="He glared at me.",
    )
    assert replace(make_occurrence(), cloze=cloze).has_results


def test_an_occurrence_never_earns_reviewed() -> None:
    with pytest.raises(InvalidEarnedSectionError):
        replace(make_occurrence(), earned_section=CandidateSection.REVIEWED)
