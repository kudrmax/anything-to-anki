from __future__ import annotations

import re
from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import CardPreviewDTO
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository


def _highlight(fragment: str, lemma: str) -> str:
    """Wrap the first occurrence of lemma in fragment with <b> tags."""
    pattern = re.compile(r"\b(" + re.escape(lemma) + r")\b", re.IGNORECASE)
    result, count = pattern.subn(r"<b>\1</b>", fragment, count=1)
    return result if count else fragment


class GetSourceCardsUseCase:
    """Builds card previews for all 'learn' candidates of a source."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
    ) -> None:
        self._candidate_repo = candidate_repo

    def execute(self, source_id: int) -> list[CardPreviewDTO]:
        candidates = self._candidate_repo.get_by_source(source_id)
        learn_candidates = [c for c in candidates if c.status == CandidateStatus.LEARN]

        cards: list[CardPreviewDTO] = []
        for candidate in learn_candidates:
            cards.append(
                CardPreviewDTO(
                    candidate_id=candidate.id,  # type: ignore[arg-type]
                    lemma=candidate.lemma,
                    sentence=_highlight(candidate.context_fragment, candidate.lemma),
                    meaning=candidate.meaning,
                    ipa=candidate.ipa,
                )
            )
        return cards
