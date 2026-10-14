from __future__ import annotations

import pytest
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import InvalidClozeError
from backend.domain.services.cloze_builder import ClozeBuilder, ClozeFrontPart
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind

from tests.phrase_support import phrase

pytestmark = pytest.mark.unit

GIVE_UP_TEXT = "She finally gave up smoking last year."
GIVE_UP = phrase(GIVE_UP_TEXT, "gave up")
GAVE_IT_UP = phrase("I gave it up at last.", "give up", lemmas={"gave": "give"})
builder = ClozeBuilder()


def _meaning(
    translation: str | None = "бросить", synonyms: str | None = "quit, stop"
) -> CandidateMeaning:
    return CandidateMeaning(
        candidate_id=1,
        meaning="To **give up** is to stop.",
        translation=translation,
        synonyms=synonyms,
        examples=None,
        ipa=None,
        generated_at=None,
    )


def _candidate(text: str, cloze: CandidateCloze | None) -> StoredCandidate:
    return StoredCandidate(
        source_id=1,
        lemma="give up",
        pos="VERB",
        cefr_level=None,
        zipf_frequency=4.0,
        source_phrase=phrase(text, "gave up"),
        occurrences=1,
        status=CandidateStatus.LEARN,
        id=1,
        cloze=cloze,
    )


def test_words_mark_target_words_including_phrasal_verb() -> None:
    words = builder.words(GIVE_UP)
    assert [w.text for w in words] == ["She", "finally", "gave", "up", "smoking", "last", "year"]
    assert [w.index for w in words if w.is_target] == [2, 3]


def test_words_mark_separated_phrasal_verb() -> None:
    words = builder.words(GAVE_IT_UP)
    assert [w.index for w in words if w.is_target] == [1, 3]


def test_words_ignore_case_and_edge_punctuation() -> None:
    words = builder.words(phrase("Procrastinate, they said.", "procrastinate"))
    assert [w.index for w in words if w.is_target] == [0]


def test_default_hidden_is_target_words() -> None:
    assert builder.default_hidden(GIVE_UP) == (2, 3)


def test_validate_rejects_empty_and_out_of_range() -> None:
    with pytest.raises(InvalidClozeError):
        builder.validate(GIVE_UP, ())
    with pytest.raises(InvalidClozeError):
        builder.validate(GIVE_UP, (7,))
    builder.validate(GIVE_UP, (3,))


def test_cloze_text_merges_adjacent_words_and_keeps_punctuation_outside() -> None:
    assert builder.cloze_text(GIVE_UP, (2, 3)) == "She finally {{c1::gave up}} smoking last year."
    assert builder.cloze_text(GIVE_UP, (6,)) == "She finally gave up smoking last {{c1::year}}."


def test_cloze_text_uses_same_number_for_separated_parts() -> None:
    assert (
        builder.cloze_text(GAVE_IT_UP, (1, 3))
        == "I {{c1::gave}} it {{c1::up}} at last."
    )


def test_cloze_text_keeps_inner_apostrophe_and_outer_quotes() -> None:
    cloze = builder.cloze_text(phrase('He said "don\'t" twice'), (2,))
    assert cloze == 'He said "{{c1::don\'t}}" twice'


def test_cloze_text_escapes_anki_syntax() -> None:
    text = builder.cloze_text(phrase("a::b c}}d end"), (0, 1, 2, 3))
    assert "{{c1::" in text
    assert text.count("::") == 1  # only the c1 separator survives
    assert text.count("}}") == 1


def test_cloze_text_puts_each_hint_into_its_gap() -> None:
    assert (
        builder.cloze_text(GAVE_IT_UP, (1, 3), ["g…", "u…"])
        == "I {{c1::gave::g…}} it {{c1::up::u…}} at last."
    )
    assert (
        builder.cloze_text(GAVE_IT_UP, (1, 3), ["бросить", ""])
        == "I {{c1::gave::бросить}} it {{c1::up}} at last."
    )


def test_cloze_text_escapes_anki_syntax_in_hint() -> None:
    text = builder.cloze_text(GIVE_UP, (6,), ["a::b}}"])
    assert text.count("::") == 2
    assert text.count("}}") == 1


def test_front_shows_gaps_without_hint() -> None:
    assert builder.front(GIVE_UP, (2, 3)) == [
        ClozeFrontPart("She finally ", is_gap=False),
        ClozeFrontPart("[…]", is_gap=True),
        ClozeFrontPart(" smoking last year.", is_gap=False),
    ]


def test_front_shows_hint_inside_gap_and_keeps_punctuation_outside() -> None:
    assert builder.front(phrase('"Year," she said'), (0,), ["y…"]) == [
        ClozeFrontPart('"', is_gap=False),
        ClozeFrontPart("[y…]", is_gap=True),
        ClozeFrontPart('," she said', is_gap=False),
    ]


def test_gap_hints_first_letter_per_gap() -> None:
    hints = builder.gap_hints(
        ClozeHintKind.FIRST_LETTER, _meaning(), GAVE_IT_UP, (1, 3), None
    )
    assert hints == ["g…", "u…"]
    assert builder.gap_hints(ClozeHintKind.FIRST_LETTER, None, GIVE_UP, (2, 3), None) == [
        "g… u…"
    ]


def test_gap_hints_whole_target_hint_goes_to_first_gap() -> None:
    assert builder.gap_hints(ClozeHintKind.TRANSLATION, _meaning(), GAVE_IT_UP, (1, 3), None) == [
        "бросить",
        "",
    ]
    assert builder.gap_hints(ClozeHintKind.CUSTOM, None, GAVE_IT_UP, (1, 3), " quit ") == [
        "quit",
        "",
    ]
    assert builder.gap_hints(ClozeHintKind.NONE, _meaning(), GAVE_IT_UP, (1, 3), None) == [
        "",
        "",
    ]


def test_hint_text_variants() -> None:
    m = _meaning()
    hidden = ["up"]
    assert builder.hint_text(ClozeHintKind.NONE, m, hidden, None) == ""
    assert builder.hint_text(ClozeHintKind.TRANSLATION, m, hidden, None) == "бросить"
    assert builder.hint_text(ClozeHintKind.SYNONYMS, m, hidden, None) == "quit, stop"
    assert builder.hint_text(ClozeHintKind.FIRST_LETTER, m, ["gave", "up"], None) == "g… u…"
    assert builder.hint_text(ClozeHintKind.CUSTOM, m, hidden, "  своя  ") == "своя"


def test_hint_text_strips_markdown_bold() -> None:
    assert (
        builder.hint_text(
            ClozeHintKind.TRANSLATION, _meaning(translation="**бросить**"), ["up"], None
        )
        == "бросить"
    )


def test_available_hints_hide_leaking_and_missing() -> None:
    leaking = _meaning(synonyms="give up, quit")
    assert builder.available_hints(leaking, ["give", "up"]) == [
        ClozeHintKind.NONE,
        ClozeHintKind.TRANSLATION,
        ClozeHintKind.FIRST_LETTER,
        ClozeHintKind.CUSTOM,
    ]
    assert builder.available_hints(None, ["up"]) == [
        ClozeHintKind.NONE,
        ClozeHintKind.FIRST_LETTER,
        ClozeHintKind.CUSTOM,
    ]


def test_available_hints_leak_check_uses_word_boundaries() -> None:
    # "up" inside "upset" is not a leak
    assert ClozeHintKind.SYNONYMS in builder.available_hints(
        _meaning(synonyms="upset, quit"), ["up"]
    )


def test_effective_keeps_markup_for_same_phrase() -> None:
    cloze = CandidateCloze(1, (3,), ClozeHintKind.TRANSLATION, None, GIVE_UP_TEXT)
    assert builder.effective(_candidate(GIVE_UP_TEXT, cloze)) == cloze


def test_effective_rebuilds_markup_for_changed_phrase() -> None:
    cloze = CandidateCloze(1, (3,), ClozeHintKind.TRANSLATION, None, GIVE_UP_TEXT)
    new_phrase = "Finally she gave up."
    result = builder.effective(_candidate(new_phrase, cloze))
    assert result == CandidateCloze(1, (2, 3), ClozeHintKind.TRANSLATION, None, new_phrase)


def test_effective_without_cloze_is_none() -> None:
    assert builder.effective(_candidate(GIVE_UP_TEXT, None)) is None


def test_highlight_hidden_wraps_runs_and_keeps_punctuation_outside() -> None:
    highlight = builder.highlight_hidden
    assert highlight(GIVE_UP, (3,)) == "She finally gave <b>up</b> smoking last year."
    assert highlight(GIVE_UP, (2, 3)) == "She finally <b>gave up</b> smoking last year."
    assert highlight(GIVE_UP, (6,)) == "She finally gave up smoking last <b>year</b>."
