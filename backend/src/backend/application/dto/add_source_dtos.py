from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.domain.value_objects.format import Format  # noqa: TC001 — Pydantic runtime
from backend.domain.value_objects.input_kind import InputKind  # noqa: TC001 — Pydantic runtime
from backend.domain.value_objects.input_problem import (
    InputProblem,  # noqa: TC001 — Pydantic runtime
)

if TYPE_CHECKING:
    from backend.domain.value_objects.question import Question, QuestionOption


class DetailItemDTO(BaseModel):
    text: str
    note: str | None


class OptionDetailsDTO(BaseModel):
    title: str
    items: list[DetailItemDTO]


class QuestionOptionDTO(BaseModel):
    id: str
    label: str
    details: OptionDetailsDTO | None

    @staticmethod
    def from_option(option: QuestionOption) -> QuestionOptionDTO:
        details = option.details
        return QuestionOptionDTO(
            id=option.id,
            label=option.label,
            details=OptionDetailsDTO(
                title=details.title,
                items=[DetailItemDTO(text=item.text, note=item.note) for item in details.items],
            )
            if details
            else None,
        )


class QuestionDTO(BaseModel):
    """A question about the inputs it lists; one answer goes to each of them. The label names
    the input when several are added at once and the question is about one of them."""

    id: str
    prompt: str
    options: list[QuestionOptionDTO]
    default: str
    input_indexes: list[int] = [0]
    input_label: str | None = None

    @staticmethod
    def from_question(
        question: Question, input_index: int = 0, input_label: str | None = None,
    ) -> QuestionDTO:
        return QuestionDTO(
            id=question.id,
            prompt=question.prompt,
            options=[QuestionOptionDTO.from_option(option) for option in question.options],
            default=question.default,
            input_indexes=[input_index],
            input_label=input_label,
        )

    def same_as(self, other: QuestionDTO) -> bool:
        """Asks the same thing with the same choices, whichever input it is about."""
        return (self.id, self.prompt, self.default, self.options) == (
            other.id, other.prompt, other.default, other.options,
        )


class QuestionsRequired(BaseModel):
    """The input can't become sources until the user answers these."""

    questions: list[QuestionDTO]


class CollectionChoiceDTO(BaseModel):
    """An existing collection, a new one by name; neither — no collection."""

    existing_id: int | None = None
    new_name: str | None = None


class NamingItemDTO(BaseModel):
    """A source about to be made: where it comes from and what it is called when added alone."""

    label: str
    own_title: str
    words: int


class NamingVariableDTO(BaseModel):
    token: str
    label: str


class NumberFormatDTO(BaseModel):
    """A way to write `{{n}}`: zeros up to `digits`; no digits — as many as the count needs."""

    digits: int | None
    label: str


class NamingRequired(BaseModel):
    """The input becomes several sources; the user picks their collection and titles."""

    heading: str
    items: list[NamingItemDTO]
    default_collection: CollectionChoiceDTO | None
    default_rule: str
    variables: list[NamingVariableDTO]
    number_formats: list[NumberFormatDTO]


class SourcesCreated(BaseModel):
    """Sources made from one add; several are gathered in the chosen collection."""

    source_ids: list[int]
    collection_id: int | None = None


class InputDescriptionDTO(BaseModel):
    """What the Add screen input becomes: its kind, how a source will be read, or why it
    can't be added.

    Empty input has no description: every field is empty. `several` — files added at once.
    """

    kind: InputKind | None = None
    format: Format | None = None
    several: bool | None = None
    label: str | None = None
    problem: InputProblem | None = None
    problem_message: str | None = None
    problem_hint: str | None = None


class NamingDTO(BaseModel):
    """How the user named the sources of one add; `titles` are rows rewritten by hand, by
    row index."""

    collection: CollectionChoiceDTO | None = None
    rule: str
    titles: dict[int, str] = {}
    number_digits: int | None = None


class AddSourceRequest(BaseModel):
    """What the user put in the input field, with every answer given so far, one set of
    answers per input, and the naming once it was asked."""

    text: str
    subtitles_path: str | None = None
    title: str | None = None
    answers: list[dict[str, str]] = []
    naming: NamingDTO | None = None


class RenderNamesRequest(BaseModel):
    rule: str
    collection_name: str | None = None
    own_titles: list[str]
    number_digits: int | None = None


class DescribeInputRequest(BaseModel):
    text: str


class CreateTopicRequest(BaseModel):
    query: str
    title: str | None = None
