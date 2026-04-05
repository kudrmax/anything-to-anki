from __future__ import annotations

from pydantic import BaseModel, field_validator

from backend.domain.value_objects.candidate_status import CandidateStatus


class AddManualCandidateRequest(BaseModel):
    """Input for manually adding a candidate during review."""

    surface_form: str
    context_fragment: str


class MarkCandidateRequest(BaseModel):
    """Input for marking a candidate status."""

    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        normalized = v.strip().lower()
        valid = {s.value for s in CandidateStatus} - {CandidateStatus.PENDING.value}
        if normalized not in valid:
            msg = f"Invalid status: {v}. Must be one of: {', '.join(sorted(valid))}"
            raise ValueError(msg)
        return normalized
