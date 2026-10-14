from __future__ import annotations

from pydantic import BaseModel, field_validator

from backend.domain.value_objects.candidate_status import CandidateStatus


class SelectionDTO(BaseModel):
    """Text the user selected on the source screen; characters in code points, end exclusive."""

    start_block: int
    start_line: int
    start_char: int
    end_block: int
    end_line: int
    end_char: int

    @property
    def start(self) -> tuple[int, int, int]:
        return (self.start_block, self.start_line, self.start_char)

    @property
    def end(self) -> tuple[int, int, int]:
        return (self.end_block, self.end_line, self.end_char)


class AddManualCandidateRequest(BaseModel):
    """Words the user picked, by their numbers, in a phrase they selected on the source screen."""

    target_words: list[int]
    selection: SelectionDTO


class AddSavedPhraseRequest(BaseModel):
    """Input for saving a phrase met anywhere, with the target words picked in it by number."""

    phrase: str
    target_words: list[int]


class SetPhraseBoundaryRequest(BaseModel):
    """The phrase of a candidate, selected anew on the source screen."""

    selection: SelectionDTO


class ReplaceWithExampleRequest(BaseModel):
    """Input for replacing a candidate's phrase with an AI-generated example."""

    example_text: str


class RevertPolishRequest(BaseModel):
    """Input for showing the source phrase (True) or AI's polished one (False)."""

    reverted: bool


class EditPhraseRequest(BaseModel):
    """Input for rewriting the card phrase by hand."""

    phrase: str


class MarkCandidateRequest(BaseModel):
    """Input for marking a candidate status."""

    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        normalized = v.strip().lower()
        valid = {s.value for s in CandidateStatus}
        if normalized not in valid:
            msg = f"Invalid status: {v}. Must be one of: {', '.join(sorted(valid))}"
            raise ValueError(msg)
        return normalized
