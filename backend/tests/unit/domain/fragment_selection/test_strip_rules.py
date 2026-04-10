from backend.domain.entities.token_data import TokenData
from backend.domain.services.fragment_selection.cleanup.rules import (
    Edge,
    LeftCconjSconjRule,
    LeftRelativizerRule,
    PunctuationRule,
    RightCconjSconjDetIntjRule,
    RightDanglingAdpRule,
    RightDanglingAuxPartRule,
    RightDanglingSubjectPronounRule,
    RightPossessivePronounRule,
    RightRelativePronounRule,
)
from backend.domain.value_objects.fragment_selection_config import CleanupConfig


def _tok(
    index: int,
    text: str,
    pos: str = "NOUN",
    *,
    tag: str | None = None,
    is_punct: bool = False,
    is_alpha: bool = True,
    children: tuple[int, ...] = (),
    head_index: int | None = None,
    dep: str = "",
) -> TokenData:
    return TokenData(
        index=index,
        text=text,
        lemma=text.lower(),
        pos=pos,
        tag=tag if tag is not None else pos,
        head_index=head_index if head_index is not None else index,
        children_indices=children,
        is_punct=is_punct,
        is_stop=False,
        is_alpha=is_alpha,
        is_propn=False,
        sent_index=0,
        dep=dep,
    )


# --- PunctuationRule -----------------------------------------------------


def test_punctuation_rule_strips_comma_on_right() -> None:
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [
        _tok(5, ",", "PUNCT", is_punct=True, is_alpha=False),
    ]
    rule = PunctuationRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is True


def test_punctuation_rule_keeps_sentence_final_period() -> None:
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [
        _tok(5, ".", "PUNCT", is_punct=True, is_alpha=False),
    ]
    rule = PunctuationRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is False


def test_punctuation_rule_strips_comma_on_left() -> None:
    tokens = [_tok(0, ",", "PUNCT", is_punct=True, is_alpha=False)] + [
        _tok(i, f"w{i}") for i in range(1, 6)
    ]
    rule = PunctuationRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.LEFT) is True


# --- LeftCconjSconjRule --------------------------------------------------


def test_left_cconj_sconj_rule_strips_but() -> None:
    tokens = [_tok(0, "but", "CCONJ")] + [
        _tok(i, f"w{i}") for i in range(1, 6)
    ]
    rule = LeftCconjSconjRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.LEFT) is True


def test_left_cconj_sconj_rule_does_not_apply_on_right() -> None:
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [_tok(5, "but", "CCONJ")]
    rule = LeftCconjSconjRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is False


# --- LeftRelativizerRule -------------------------------------------------


def test_left_relativizer_strips_bare_that() -> None:
    tokens = [
        _tok(0, "that", "SCONJ"),
        _tok(1, "is", "VERB"),
    ] + [_tok(i, f"w{i}") for i in range(2, 6)]
    rule = LeftRelativizerRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.LEFT) is True


def test_left_relativizer_keeps_demonstrative_that_man() -> None:
    tokens = [
        _tok(0, "that", "DET"),
        _tok(1, "man", "NOUN"),
    ] + [_tok(i, f"w{i}") for i in range(2, 6)]
    rule = LeftRelativizerRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.LEFT) is False


# --- RightCconjSconjDetIntjRule ------------------------------------------


def test_right_cconj_sconj_det_intj_strips_trailing_and() -> None:
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [_tok(5, "and", "CCONJ")]
    rule = RightCconjSconjDetIntjRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is True


def test_right_cconj_sconj_det_intj_strips_trailing_intj() -> None:
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [_tok(5, "please", "INTJ")]
    rule = RightCconjSconjDetIntjRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is True


# --- RightDanglingAdpRule ------------------------------------------------


def test_right_dangling_adp_strips_preposition_without_object() -> None:
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [_tok(5, "with", "ADP")]
    rule = RightDanglingAdpRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is True


def test_right_dangling_adp_keeps_preposition_with_object_inside() -> None:
    with_tok = _tok(5, "with", "ADP", children=(4,))
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [with_tok]
    rule = RightDanglingAdpRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is False


# --- RightDanglingSubjectPronounRule -------------------------------------


def test_right_dangling_subject_pronoun_strips_nsubj_you() -> None:
    you = _tok(5, "you", "PRON", tag="PRP", head_index=99, dep="nsubj")
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [you]
    rule = RightDanglingSubjectPronounRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is True


def test_right_dangling_subject_pronoun_keeps_object_with_you() -> None:
    you = _tok(5, "you", "PRON", tag="PRP", head_index=4, dep="pobj")
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [you]
    rule = RightDanglingSubjectPronounRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is False


# --- RightRelativePronounRule --------------------------------------------


def test_right_relative_pronoun_strips_trailing_that() -> None:
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [_tok(5, "that", "PRON")]
    rule = RightRelativePronounRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is True


# --- RightPossessivePronounRule ------------------------------------------


def test_right_possessive_pronoun_strips_trailing_its() -> None:
    its = _tok(5, "its", "PRON", tag="PRP$")
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [its]
    rule = RightPossessivePronounRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is True


# --- RightDanglingAuxPartRule --------------------------------------------


def test_right_dangling_aux_part_strips_trailing_have_aux() -> None:
    have = _tok(5, "have", "AUX", tag="VB", head_index=99, dep="aux")
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [have]
    rule = RightDanglingAuxPartRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is True


def test_right_dangling_aux_part_keeps_aux_with_head_in_fragment() -> None:
    have = _tok(5, "have", "AUX", tag="VB", head_index=4, dep="aux")
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [have]
    rule = RightDanglingAuxPartRule(CleanupConfig())
    assert rule.applies(tokens, [0, 1, 2, 3, 4, 5], Edge.RIGHT) is False
