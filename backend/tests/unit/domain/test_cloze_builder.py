from __future__ import annotations

import pytest
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import InvalidClozeError
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind

pytestmark = pytest.mark.unit

GIVE_UP = "She finally gave up smoking last year."
builder = ClozeBuilder()


def _meaning(
    translation: str | None = "бросить", synonyms: str | None = "quit, stop"
) -> CandidateMeaning:
    # Посмотри конструктор CandidateMeaning в domain/entities/candidate_meaning.py
    # и передай остальные обязательные поля нейтральными значениями.
    return CandidateMeaning(
        candidate_id=1,
        meaning="To **give up** is to stop.",
        translation=translation,
        synonyms=synonyms,
        examples=None,
        ipa=None,
        generated_at=None,
    )


def _candidate(
    phrase: str, lemma: str, surface: str | None, cloze: CandidateCloze | None
) -> StoredCandidate:
    return StoredCandidate(
        source_id=1,
        lemma=lemma,
        pos="VERB",
        cefr_level=None,
        zipf_frequency=4.0,
        context_fragment=phrase,
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.LEARN,
        surface_form=surface,
        id=1,
        cloze=cloze,
    )


def test_words_mark_target_words_including_phrasal_verb() -> None:
    words = builder.words(GIVE_UP, "give up", "gave up")
    assert [w.text for w in words] == ["She", "finally", "gave", "up", "smoking", "last", "year."]
    assert [w.index for w in words if w.is_target] == [2, 3]


def test_words_mark_separated_phrasal_verb() -> None:
    words = builder.words("I gave it up at last.", "give up", "gave up")
    assert [w.index for w in words if w.is_target] == [1, 3]


def test_words_ignore_case_and_edge_punctuation() -> None:
    words = builder.words("Procrastinate, they said.", "procrastinate", None)
    assert [w.index for w in words if w.is_target] == [0]


def test_default_hidden_is_target_words() -> None:
    assert builder.default_hidden(builder.words(GIVE_UP, "give up", "gave up")) == (2, 3)


def test_validate_rejects_empty_and_out_of_range() -> None:
    words = builder.words(GIVE_UP, "give up", "gave up")
    with pytest.raises(InvalidClozeError):
        builder.validate(words, ())
    with pytest.raises(InvalidClozeError):
        builder.validate(words, (7,))
    builder.validate(words, (3,))


def test_cloze_text_merges_adjacent_words_and_keeps_punctuation_outside() -> None:
    assert builder.cloze_text(GIVE_UP, (2, 3)) == "She finally {{c1::gave up}} smoking last year."
    assert builder.cloze_text(GIVE_UP, (6,)) == "She finally gave up smoking last {{c1::year}}."


def test_cloze_text_uses_same_number_for_separated_parts() -> None:
    assert (
        builder.cloze_text("I gave it up at last.", (1, 3))
        == "I {{c1::gave}} it {{c1::up}} at last."
    )


def test_cloze_text_keeps_inner_apostrophe_and_outer_quotes() -> None:
    assert builder.cloze_text('He said "don\'t" twice', (2,)) == 'He said "{{c1::don\'t}}" twice'


def test_cloze_text_escapes_anki_syntax() -> None:
    text = builder.cloze_text("a::b c}}d end", (0, 1))
    assert "{{c1::" in text
    assert text.count("::") == 1  # only the c1 separator survives
    assert text.count("}}") == 1


def test_front_preview_shows_gaps() -> None:
    assert builder.front_preview(GIVE_UP, (3,)) == "She finally gave […] smoking last year."
    assert builder.front_preview(GIVE_UP, (2, 3)) == "She finally […] smoking last year."


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
    cloze = CandidateCloze(1, (3,), ClozeHintKind.TRANSLATION, None, GIVE_UP)
    assert builder.effective(_candidate(GIVE_UP, "give up", "gave up", cloze)) == cloze


def test_effective_rebuilds_markup_for_changed_phrase() -> None:
    cloze = CandidateCloze(1, (3,), ClozeHintKind.TRANSLATION, None, GIVE_UP)
    new_phrase = "Finally she gave up."
    result = builder.effective(_candidate(new_phrase, "give up", "gave up", cloze))
    assert result == CandidateCloze(1, (2, 3), ClozeHintKind.TRANSLATION, None, new_phrase)


def test_effective_drops_cloze_when_target_is_gone() -> None:
    cloze = CandidateCloze(1, (3,), ClozeHintKind.NONE, None, GIVE_UP)
    assert (
        builder.effective(_candidate("Totally different text.", "give up", "gave up", cloze))
        is None
    )


def test_effective_without_cloze_is_none() -> None:
    assert builder.effective(_candidate(GIVE_UP, "give up", "gave up", None)) is None
