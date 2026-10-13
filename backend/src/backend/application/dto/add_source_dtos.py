from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.domain.value_objects.format import Format  # noqa: TC001 — Pydantic runtime

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
    id: str
    prompt: str
    options: list[QuestionOptionDTO]
    default: str

    @staticmethod
    def from_question(question: Question) -> QuestionDTO:
        return QuestionDTO(
            id=question.id,
            prompt=question.prompt,
            options=[QuestionOptionDTO.from_option(option) for option in question.options],
            default=question.default,
        )


class QuestionsRequired(BaseModel):
    """The input can't become sources until the user answers these."""

    questions: list[QuestionDTO]


class SourcesCreated(BaseModel):
    """Sources made from one input; a split book's chapters are gathered in a collection."""

    source_ids: list[int]
    collection_id: int | None = None


class DetectedFormatDTO(BaseModel):
    """How an input will be read, for the hint under the input field."""

    format: Format | None
    label: str
