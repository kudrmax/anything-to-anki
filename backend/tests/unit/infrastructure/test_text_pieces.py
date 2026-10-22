from backend.infrastructure.adapters.text_pieces import text_pieces


def _texts(text: str, limit: int) -> list[str]:
    return [text[start:end] for start, end in text_pieces(text, limit)]


class TestTextPieces:
    def test_short_text_is_one_piece(self) -> None:
        assert _texts("One line.\n\nAnother.", 100) == ["One line.\n\nAnother."]

    def test_empty_text_has_no_pieces(self) -> None:
        assert text_pieces("", 10) == []

    def test_cuts_after_the_last_blank_line_that_fits(self) -> None:
        text = "First one.\n\nSecond.\n\nThird line here."
        assert _texts(text, 25) == ["First one.\n\nSecond.\n\n", "Third line here."]

    def test_whitespace_after_a_blank_line_stays_with_the_piece_before(self) -> None:
        text = "First.\n\n\n  Second one."
        assert _texts(text, 14) == ["First.\n\n\n  ", "Second one."]

    def test_falls_back_to_a_line_break_without_a_blank_line(self) -> None:
        text = "First line\nsecond line\nthird"
        assert _texts(text, 25) == ["First line\nsecond line\n", "third"]

    def test_falls_back_to_a_space_without_a_line_break(self) -> None:
        text = "one two three four five"
        assert _texts(text, 10) == ["one two ", "three ", "four five"]

    def test_cuts_a_word_longer_than_the_limit(self) -> None:
        assert _texts("abcdefghij", 4) == ["abcd", "efgh", "ij"]

    def test_pieces_cover_the_text_and_fit_the_limit(self) -> None:
        text = ("A sentence here.\nAnd there.\n\n" * 50) + "word " * 200 + "x" * 30
        limit = 37
        pieces = text_pieces(text, limit)
        assert "".join(text[start:end] for start, end in pieces) == text
        assert all(0 < end - start <= limit for start, end in pieces)
        assert all(a[1] == b[0] for a, b in zip(pieces, pieces[1:], strict=False))
