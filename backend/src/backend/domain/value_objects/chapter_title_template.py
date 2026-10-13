from __future__ import annotations

from dataclasses import dataclass

BOOK_NAME_PLACEHOLDER = "{{book_name}}"
CHAPTER_NUMBER_PLACEHOLDER = "{{n}}"
CHAPTER_TITLE_PLACEHOLDER = "{{chapter_title}}"
DEFAULT_CHAPTER_TITLE_TEMPLATE = f"{BOOK_NAME_PLACEHOLDER} ch{CHAPTER_NUMBER_PLACEHOLDER}"
# Without one of these every chapter of a book would get the same title.
DISTINGUISHING_PLACEHOLDERS: tuple[str, ...] = (
    CHAPTER_NUMBER_PLACEHOLDER,
    CHAPTER_TITLE_PLACEHOLDER,
)


@dataclass(frozen=True)
class ChapterTitleTemplate:
    """How a source made from a book's chapter is titled, e.g. `{{book_name}} ch{{n}}`."""

    pattern: str

    def __post_init__(self) -> None:
        if not any(placeholder in self.pattern for placeholder in DISTINGUISHING_PLACEHOLDERS):
            msg = (
                f"Chapter title template must contain {CHAPTER_NUMBER_PLACEHOLDER}"
                f" or {CHAPTER_TITLE_PLACEHOLDER}"
            )
            raise ValueError(msg)

    def render(self, book_name: str, number: int, chapter_title: str | None) -> str:
        title = (
            self.pattern.replace(BOOK_NAME_PLACEHOLDER, book_name)
            .replace(CHAPTER_NUMBER_PLACEHOLDER, str(number))
            .replace(CHAPTER_TITLE_PLACEHOLDER, chapter_title or f"Chapter {number}")
        )
        return " ".join(title.split())
