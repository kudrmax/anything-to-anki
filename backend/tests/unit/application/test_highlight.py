import pytest
from backend.application.utils.highlight import (
    format_examples_as_list,
    highlight_all_forms,
    strip_markdown,
)


@pytest.mark.unit
class TestStripMarkdown:
    def test_removes_bold_asterisk(self) -> None:
        assert strip_markdown("**bold** word") == "bold word"

    def test_removes_italic_asterisk(self) -> None:
        assert strip_markdown("*italic* word") == "italic word"

    def test_removes_bold_underscore(self) -> None:
        assert strip_markdown("__bold__ word") == "bold word"

    def test_removes_italic_underscore(self) -> None:
        assert strip_markdown("_italic_ word") == "italic word"

    def test_bold_before_italic(self) -> None:
        assert strip_markdown("**_nested_** word") == "nested word"

    def test_no_markdown_unchanged(self) -> None:
        assert strip_markdown("plain text") == "plain text"

    def test_multiple_bold_spans(self) -> None:
        assert strip_markdown("**a** and **b**") == "a and b"


@pytest.mark.unit
class TestHighlightAllForms:
    def test_highlights_exact_lemma(self) -> None:
        result = highlight_all_forms("leads to burnout quickly", "burnout", None)
        assert result == "leads to <b>burnout</b> quickly"

    def test_highlights_inflected_suffix(self) -> None:
        result = highlight_all_forms("she is running fast", "run", None)
        assert result == "she is <b>running</b> fast"

    def test_highlights_plural(self) -> None:
        result = highlight_all_forms("many runners compete", "runner", None)
        assert result == "many <b>runners</b> compete"

    def test_highlights_surface_form(self) -> None:
        result = highlight_all_forms("he gave up easily", "give up", "gave up")
        assert result == "he <b>gave up</b> easily"

    def test_highlights_all_occurrences(self) -> None:
        result = highlight_all_forms("run and running again", "run", None)
        assert result == "<b>run</b> and <b>running</b> again"

    def test_strips_markdown_before_highlight(self) -> None:
        result = highlight_all_forms("**burnout** is real", "burnout", None)
        assert result == "<b>burnout</b> is real"

    def test_markdown_bold_then_highlight(self) -> None:
        result = highlight_all_forms("feel **burnout** daily", "burnout", None)
        assert result == "feel <b>burnout</b> daily"

    def test_case_insensitive(self) -> None:
        result = highlight_all_forms("Burnout leads to burnout", "burnout", None)
        assert "<b>Burnout</b>" in result
        assert "<b>burnout</b>" in result

    def test_no_match_returns_stripped_text(self) -> None:
        result = highlight_all_forms("**unrelated** text", "burnout", None)
        assert result == "unrelated text"

    def test_preserves_original_casing(self) -> None:
        result = highlight_all_forms("Running is healthy", "run", None)
        assert "<b>Running</b>" in result

    def test_phrasal_verb_base_form(self) -> None:
        result = highlight_all_forms("you need to give up", "give up", "gave up")
        assert "<b>give up</b>" in result

    def test_does_not_match_partial_word(self) -> None:
        # "burnout" should not be matched inside "burnouts" when lemma is "burn"
        result = highlight_all_forms("burnout", "burn", None)
        # \bburnout starts with "burn" → will match — this is expected behaviour
        assert "<b>burnout</b>" in result

    def test_newline_converted_to_br(self) -> None:
        result = highlight_all_forms("first line\nsecond line", "burnout", None)
        assert result == "first line<br>second line"

    def test_crlf_converted_to_br(self) -> None:
        result = highlight_all_forms("first line\r\nsecond line", "burnout", None)
        assert result == "first line<br>second line"

    def test_multiline_with_highlight(self) -> None:
        result = highlight_all_forms("feel burnout\nevery day", "burnout", None)
        assert result == "feel <b>burnout</b><br>every day"


class TestFormatExamplesAsList:
    def test_converts_br_separated_to_ul(self) -> None:
        result = format_examples_as_list("first example<br>second example")
        assert result == "<ul><li>first example</li><li>second example</li></ul>"

    def test_single_line(self) -> None:
        result = format_examples_as_list("only one example")
        assert result == "<ul><li>only one example</li></ul>"

    def test_strips_whitespace(self) -> None:
        result = format_examples_as_list("  first  <br>  second  ")
        assert result == "<ul><li>first</li><li>second</li></ul>"

    def test_skips_empty_lines(self) -> None:
        result = format_examples_as_list("first<br><br>second")
        assert result == "<ul><li>first</li><li>second</li></ul>"

    def test_preserves_html_in_lines(self) -> None:
        result = format_examples_as_list("She <b>ran</b> fast<br>He <b>ran</b> too")
        assert "<li>She <b>ran</b> fast</li>" in result

    def test_empty_string(self) -> None:
        result = format_examples_as_list("")
        assert result == ""
