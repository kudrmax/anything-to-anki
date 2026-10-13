import pytest
from backend.domain.value_objects.chapter_title_template import (
    DEFAULT_CHAPTER_TITLE_TEMPLATE,
    ChapterTitleTemplate,
)


@pytest.mark.unit
class TestChapterTitleTemplate:
    def test_default_names_chapters_by_book_and_number(self) -> None:
        template = ChapterTitleTemplate(DEFAULT_CHAPTER_TITLE_TEMPLATE)
        assert template.render("Dune", 3, "The Desert") == "Dune ch3"

    def test_fills_chapter_title(self) -> None:
        template = ChapterTitleTemplate("{{book_name}} {{n}}. {{chapter_title}}")
        assert template.render("Dune", 3, "The Desert") == "Dune 3. The Desert"

    def test_untitled_chapter_is_called_by_its_number(self) -> None:
        template = ChapterTitleTemplate("{{book_name}}: {{chapter_title}}")
        assert template.render("Dune", 3, None) == "Dune: Chapter 3"

    def test_rejects_template_giving_every_chapter_the_same_title(self) -> None:
        with pytest.raises(ValueError, match="must contain"):
            ChapterTitleTemplate("{{book_name}}")
