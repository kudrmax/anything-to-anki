from __future__ import annotations

from pydantic import BaseModel


class FollowUpRequest(BaseModel):
    """Optional body for POST /candidates/{id}/generate-meaning.

    When present, triggers a follow-up action instead of a fresh generation.
    """

    action: str
    text: str | None = None
