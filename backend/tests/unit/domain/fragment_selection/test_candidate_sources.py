from backend.domain.entities.token_data import TokenData
from backend.domain.services.fragment_selection.candidate import Candidate
from backend.domain.services.fragment_selection.sources.ancestor_chain import (
    AncestorChainSource,
)
from backend.domain.services.fragment_selection.sources.legacy_extractor import (
    LegacyExtractorSource,
)
from backend.domain.services.fragment_selection.sources.sentence import (
    SentenceSource,
)
from backend.domain.services.fragment_selection.sources.verb_subtree import (
    VerbSubtreeSource,
)


def _tok(
    index: int,
    text: str,
    pos: str,
    *,
    tag: str | None = None,
    children: tuple[int, ...] = (),
    head_index: int | None = None,
    sent_index: int = 0,
) -> TokenData:
    return TokenData(
        index=index,
        text=text,
        lemma=text.lower(),
        pos=pos,
        tag=tag if tag is not None else pos,
        head_index=head_index if head_index is not None else index,
        children_indices=children,
        is_punct=False,
        is_stop=False,
        is_alpha=True,
        is_propn=False,
        sent_index=sent_index,
        dep="",
    )


# --- VerbSubtreeSource ---------------------------------------------------


def test_verb_subtree_source_returns_piece_containing_target() -> None:
    tokens = [
        _tok(0, "She", "PRON"),
        _tok(1, "runs", "VERB", tag="VBZ", children=(0, 2)),
        _tok(2, "fast", "ADV"),
    ]
    source = VerbSubtreeSource()
    cands = list(source.generate(tokens, target_index=2))
    assert len(cands) == 1
    assert isinstance(cands[0], Candidate)
    assert cands[0].indices == (0, 1, 2)
    assert cands[0].source_name == "verb_subtree"


def test_verb_subtree_source_skips_piece_not_containing_target() -> None:
    tokens = [
        _tok(0, "runs", "VERB", tag="VBZ"),
        _tok(1, "jumps", "VERB", tag="VBZ", children=(2,)),
        _tok(2, "high", "ADV"),
    ]
    source = VerbSubtreeSource()
    cands = list(source.generate(tokens, target_index=2))
    assert len(cands) == 1
    assert cands[0].indices == (1, 2)


# --- AncestorChainSource -------------------------------------------------


def test_ancestor_chain_source_yields_target_and_each_ancestor() -> None:
    tokens = [
        _tok(0, "a", "NOUN", head_index=1),
        _tok(1, "b", "VERB", tag="VBZ", head_index=2, children=(0,)),
        _tok(2, "c", "VERB", tag="VBZ", head_index=2, children=(1,)),
    ]
    cands = list(AncestorChainSource().generate(tokens, target_index=0))
    indices_sets = [c.indices for c in cands]
    assert (0,) in indices_sets
    assert (0, 1) in indices_sets
    assert (0, 1, 2) in indices_sets
    assert all(c.source_name == "ancestor_chain" for c in cands)


# --- SentenceSource ------------------------------------------------------


def test_sentence_source_returns_full_sentence() -> None:
    tokens = [
        _tok(0, "a", "DET", sent_index=0),
        _tok(1, "b", "NOUN", sent_index=0),
        _tok(2, "c", "VERB", tag="VBZ", sent_index=0),
        _tok(3, "d", "NOUN", sent_index=1),
    ]
    cands = list(SentenceSource().generate(tokens, target_index=1))
    assert len(cands) == 1
    assert cands[0].indices == (0, 1, 2)
    assert cands[0].source_name == "sentence"


# --- LegacyExtractorSource -----------------------------------------------


def test_legacy_extractor_source_uses_whole_short_sentence() -> None:
    tokens = [
        _tok(0, "The", "DET", sent_index=0),
        _tok(1, "cat", "NOUN", sent_index=0),
        _tok(2, "sleeps", "VERB", tag="VBZ", sent_index=0),
    ]
    cands = list(LegacyExtractorSource().generate(tokens, target_index=1))
    assert len(cands) == 1
    assert cands[0].indices == (0, 1, 2)
    assert cands[0].source_name == "legacy_extractor"
