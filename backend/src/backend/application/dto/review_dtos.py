from __future__ import annotations

from pydantic import BaseModel

from backend.application.dto.source_dtos import ProgressDTO  # noqa: TC001 — pydantic field type


class ReviewHeaderDTO(BaseModel):
    """What the review screen of a set of sources shows above its cards, for the whole set."""

    # The set's token, as the scope query parameter takes it back.
    scope: str
    title: str
    status: str
    progress: ProgressDTO
    learn_count: int  # words to learn
    # Some source of the set is held by an operation: its cards wait for it.
    busy: bool
    # A shown card's meaning failed because the AI is not available from here.
    ai_unavailable: bool
