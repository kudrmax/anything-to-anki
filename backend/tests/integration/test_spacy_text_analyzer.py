import pytest
from backend.domain.entities.token_data import TokenData
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

    def test_blank_line_ends_a_sentence(self) -> None:
        tokens = self.analyzer.analyze("The Birth of a Theory\n\nIt started in secret.")
        heading = {t.sent_index for t in tokens if t.text in ("Birth", "Theory")}
        body = {t.sent_index for t in tokens if t.text in ("started", "secret")}
        assert len(heading) == len(body) == 1
        assert heading != body

    def test_text_longer_than_a_piece_is_parsed_in_pieces_as_one_text(self) -> None:
        text = "\n\n".join(
            f"Paragraph {n} tells how the cat sat on the mat. It was happy." for n in range(12)
        )
        whole = self.analyzer.analyze(text)
        pieced = SpaCyTextAnalyzer(piece_length=150).analyze(text)

        def layout(tokens: list[TokenData]) -> list[tuple[object, ...]]:
            return [
                (t.index, t.text, t.char_start, t.whitespace_after, t.sent_index,
                 t.head_index, t.children_indices)
                for t in tokens
            ]

        assert layout(pieced) == layout(whole)
        assert all(text[t.char_start:t.char_end] == t.text for t in pieced)

    def test_text_without_blank_lines_is_parsed_in_pieces(self) -> None:
        analyzer = SpaCyTextAnalyzer(piece_length=40)
        text = "The cat sat on the mat. " * 20
        tokens = analyzer.analyze(text)
        assert [t.index for t in tokens] == list(range(len(tokens)))
        assert all(text[t.char_start:t.char_end] == t.text for t in tokens)
        assert all(0 <= t.head_index < len(tokens) for t in tokens)

    def test_reports_the_share_parsed_after_each_piece(self) -> None:
        text = "The cat sat on the mat. " * 20
        parts: list[float] = []

        SpaCyTextAnalyzer(piece_length=100).analyze(text, parts.append)

        assert len(parts) > 1
        assert parts == sorted(parts)
        assert parts[-1] == 1.0

    def test_single_line_break_does_not_end_a_sentence(self) -> None:
        tokens = self.analyzer.analyze("I told him that\nwe would come back tomorrow.")
        assert len({t.sent_index for t in tokens}) == 1
