from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class DetailItem:
    text: str
    note: str | None = None


@dataclass(frozen=True)
class OptionDetails:
    """What choosing an option leads to, e.g. the chapters a book is split into."""

    title: str
    items: tuple[DetailItem, ...]


@dataclass(frozen=True)
class QuestionOption:
    id: str
    label: str
    details: OptionDetails | None = None


@dataclass(frozen=True)
class Question:
    """Something the user has to choose before a source can be added."""

    id: str
    prompt: str
    options: tuple[QuestionOption, ...]
    default: str

    def __post_init__(self) -> None:
        if self.default not in self.option_ids:
            msg = f"Default {self.default!r} is not an option of question {self.id!r}"
            raise ValueError(msg)

    @property
    def option_ids(self) -> tuple[str, ...]:
        return tuple(option.id for option in self.options)


@dataclass(frozen=True)
class Answers:
    """The options the user chose, by question id."""

    chosen: Mapping[str, str] = field(default_factory=dict)

    def get(self, question_id: str) -> str | None:
        return self.chosen.get(question_id)

    def has(self, question_id: str) -> bool:
        return question_id in self.chosen
