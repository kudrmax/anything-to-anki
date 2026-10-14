from dataclasses import replace

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
