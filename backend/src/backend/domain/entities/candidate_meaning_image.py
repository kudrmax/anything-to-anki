from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateMeaningImage:
    """A picture of the target that shows its meaning (1:1 with a candidate).

    The user picks it from the search results or pastes it. It goes to the
    back of the card, next to the meaning; the video frame of the phrase is
    a separate picture (see CandidateMedia).
    """

    candidate_id: int
    image_path: str
