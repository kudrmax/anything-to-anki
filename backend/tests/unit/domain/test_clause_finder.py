import pytest
from backend.domain.entities.token_data import TokenData
from backend.domain.services.clause_finder import ClauseFinder


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
    )


@pytest.mark.unit
class TestClauseFinder:
    def setup_method(self) -> None:
        self.finder = ClauseFinder()

    def test_finite_verb_subtree_is_a_piece(self) -> None:
        # "I gave up" — VBD finite verb
        tokens = [
            _tok(0, "I", "PRON", head_index=1),
            _tok(1, "gave", "VERB", tag="VBD", children=(0, 2)),
            _tok(2, "up", "ADP", head_index=1),
        ]
        pieces = self.finder.find_pieces(tokens)
        assert pieces == [[0, 1, 2]]

    def test_gerund_subtree_is_a_piece_level_2(self) -> None:
        # "forming me" — VBG gerund (non-finite, Level 2)
        tokens = [
            _tok(0, "forming", "VERB", tag="VBG", children=(1,)),
            _tok(1, "me", "PRON", head_index=0),
        ]
        pieces = self.finder.find_pieces(tokens)
        assert pieces == [[0, 1]]

    def test_past_participle_subtree_is_a_piece_level_2(self) -> None:
        # "Defamed by news" — VBN past participle (Level 2)
        tokens = [
            _tok(0, "Defamed", "VERB", tag="VBN", children=(1,)),
            _tok(1, "by", "ADP", head_index=0, children=(2,)),
            _tok(2, "news", "NOUN", head_index=1),
        ]
        pieces = self.finder.find_pieces(tokens)
        assert pieces == [[0, 1, 2]]

    def test_skips_non_verbs(self) -> None:
        # "the cat" — no verbs
        tokens = [
            _tok(0, "the", "DET", head_index=1),
            _tok(1, "cat", "NOUN"),
        ]
        assert self.finder.find_pieces(tokens) == []

    def test_two_finite_verbs_two_pieces(self) -> None:
        # "I think she runs" — two clauses
        tokens = [
            _tok(0, "I", "PRON", head_index=1),
            _tok(1, "think", "VERB", tag="VBP", children=(0, 3)),
            _tok(2, "she", "PRON", head_index=3),
            _tok(3, "runs", "VERB", tag="VBZ", head_index=1, children=(2,)),
        ]
        pieces = self.finder.find_pieces(tokens)
        # think's subtree includes the whole thing; runs' subtree is just "she runs"
        assert [2, 3] in pieces  # she runs
        assert any(set(p) == {0, 1, 2, 3} for p in pieces)  # I think she runs

    def test_subtree_does_not_cross_sentence_boundary(self) -> None:
        # Verb in sentence 0; child accidentally in sentence 1 must be excluded
        tokens = [
            _tok(0, "ran", "VERB", tag="VBD", children=(1, 2), sent_index=0),
            _tok(1, "fast", "ADV", head_index=0, sent_index=0),
            _tok(2, "yesterday", "ADV", head_index=0, sent_index=1),
        ]
        pieces = self.finder.find_pieces(tokens)
        assert pieces == [[0, 1]]
