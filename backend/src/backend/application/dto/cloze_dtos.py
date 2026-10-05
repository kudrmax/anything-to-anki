from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel

from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind


def _known_hint_kind(value: str) -> str:
    try:
        ClozeHintKind(value)
    except ValueError as e:
        raise ValueError(f"Unknown hint_kind: {value}") from e
    return value


HintKindName = Annotated[str, AfterValidator(_known_hint_kind)]


class CandidateClozeDTO(BaseModel):
    """The user's cloze markup of a candidate."""

    hidden_word_indices: list[int]
    hint_kind: str
    custom_hint: str | None


class ClozeWordDTO(BaseModel):
    """A word of the phrase the user can hide."""

    index: int
    text: str
    is_target: bool


class ClozePreviewDTO(BaseModel):
    """How the cloze card would look with the given markup."""

    words: list[ClozeWordDTO]
    hidden_word_indices: list[int]
    hint_kind: str
    custom_hint: str | None
    front: str
    hint: str
    available_hints: list[str]


class SaveClozeRequest(BaseModel):
    """Input for saving the cloze markup of a candidate."""

    hidden_word_indices: list[int]
    hint_kind: HintKindName
    custom_hint: str | None = None


class PreviewClozeRequest(BaseModel):
    """Input for previewing the cloze markup; missing fields fall back to the saved markup."""

    hidden_word_indices: list[int] | None = None
    hint_kind: HintKindName | None = None
    custom_hint: str | None = None
