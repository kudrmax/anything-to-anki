from __future__ import annotations

from backend.domain.services.pos_mapping import map_pos_tag


class TestMapPosTag:
    def test_noun_tags(self) -> None:
        for tag in ("NN", "NNS", "NNP", "NNPS"):
            assert map_pos_tag(tag) == "noun"

    def test_verb_tags(self) -> None:
        for tag in ("VB", "VBD", "VBG", "VBN", "VBP", "VBZ"):
            assert map_pos_tag(tag) == "verb"

    def test_adjective_tags(self) -> None:
        for tag in ("JJ", "JJR", "JJS"):
            assert map_pos_tag(tag) == "adjective"

    def test_adverb_tags(self) -> None:
        for tag in ("RB", "RBR", "RBS"):
            assert map_pos_tag(tag) == "adverb"

    def test_other_tags(self) -> None:
        assert map_pos_tag("UH") == "exclamation"
        assert map_pos_tag("MD") == "modal verb"
        assert map_pos_tag("IN") == "preposition"
        assert map_pos_tag("DT") == "determiner"
        assert map_pos_tag("PRP") == "pronoun"
        assert map_pos_tag("PRP$") == "pronoun"
        assert map_pos_tag("CC") == "conjunction"

    def test_unknown_tag_returns_none(self) -> None:
        assert map_pos_tag("XYZ") is None
        assert map_pos_tag("") is None
