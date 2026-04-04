import pytest
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer


@pytest.mark.integration
class TestSpaCyTextAnalyzer:
    def setup_method(self) -> None:
        self.analyzer = SpaCyTextAnalyzer()

    def test_basic_tokenization(self) -> None:
        tokens = self.analyzer.analyze("The cat sat on the mat.")
        assert len(tokens) == 7  # The cat sat on the mat .
        assert tokens[0].text == "The"
        assert tokens[-1].is_punct is True

    def test_lemmatization(self) -> None:
        tokens = self.analyzer.analyze("running quickly")
        # "running" should lemmatize to "run"
        assert tokens[0].lemma in ("run", "running")

    def test_pos_tags_populated(self) -> None:
        tokens = self.analyzer.analyze("The cat sat.")
        # Universal POS
        assert tokens[1].pos in ("NOUN",)
        assert tokens[2].pos in ("VERB",)
        # Penn Treebank tag
        assert tokens[1].tag != ""
        assert tokens[2].tag != ""

    def test_dependency_tree(self) -> None:
        tokens = self.analyzer.analyze("The big cat sat.")
        # "big" and "The" should be children of "cat"
        cat_token = tokens[2]  # "cat"
        assert 0 in cat_token.children_indices or 1 in cat_token.children_indices

    def test_sentence_indices(self) -> None:
        tokens = self.analyzer.analyze("Hello world. Goodbye world.")
        sent_0 = [t for t in tokens if t.sent_index == 0]
        sent_1 = [t for t in tokens if t.sent_index == 1]
        assert len(sent_0) > 0
        assert len(sent_1) > 0

    def test_proper_noun_detection(self) -> None:
        tokens = self.analyzer.analyze("John went to Paris.")
        john = tokens[0]
        assert john.is_propn is True

    def test_stop_word_detection(self) -> None:
        tokens = self.analyzer.analyze("The cat is here.")
        the_token = tokens[0]
        assert the_token.is_stop is True

    def test_empty_text(self) -> None:
        tokens = self.analyzer.analyze("")
        assert tokens == []
