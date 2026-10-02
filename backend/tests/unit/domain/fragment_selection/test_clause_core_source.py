from backend.domain.entities.token_data import TokenData
from backend.domain.services.fragment_selection.sources.clause_core import (
    ClauseCoreSource,
)


def _tok(
    index: int,
    text: str,
    pos: str,
    dep: str,
    head: int,
    children: tuple[int, ...] = (),
) -> TokenData:
    return TokenData(
        index=index,
        text=text,
        lemma=text.lower(),
        pos=pos,
        tag=pos,
        head_index=head,
        children_indices=children,
        is_punct=False,
        is_stop=False,
        is_alpha=True,
        is_propn=False,
        sent_index=0,
        dep=dep,
    )


def _argument_sentence() -> list[TokenData]:
    """'I win arguments but you trust me' — 'trust' is a conj of 'win'."""
    return [
        _tok(0, "I", "PRON", "nsubj", 1),
        _tok(1, "win", "VERB", "ROOT", 1, children=(0, 2, 3, 5)),
        _tok(2, "arguments", "NOUN", "dobj", 1),
        _tok(3, "but", "CCONJ", "cc", 1),
        _tok(4, "you", "PRON", "nsubj", 5),
        _tok(5, "trust", "VERB", "conj", 1, children=(4, 6)),
        _tok(6, "me", "PRON", "dobj", 5),
    ]


def test_clause_core_drops_attached_clause() -> None:
    candidates = list(ClauseCoreSource().generate(_argument_sentence(), 2))
    assert [c.indices for c in candidates] == [(0, 1, 2)]


def test_attached_clause_yields_its_own_core() -> None:
    candidates = list(ClauseCoreSource().generate(_argument_sentence(), 6))
    assert [c.indices for c in candidates] == [(4, 5, 6)]


def test_core_is_the_contiguous_piece_around_the_target() -> None:
    """'no need here - before you start .' — the advcl in the middle is cut,
    the dangling final '.' must not be glued to the core."""
    tokens = [
        _tok(0, "no", "DET", "det", 1),
        _tok(1, "need", "NOUN", "ROOT", 1, children=(0, 2, 3, 6)),
        _tok(2, "here", "ADV", "advmod", 1),
        _tok(3, "-", "PUNCT", "punct", 1),
        _tok(4, "you", "PRON", "nsubj", 5),
        _tok(5, "start", "VERB", "advcl", 1, children=(4,)),
        _tok(6, ".", "PUNCT", "punct", 1),
    ]
    candidates = list(ClauseCoreSource().generate(tokens, 1))
    assert candidates[0].indices == (0, 1, 2, 3)
