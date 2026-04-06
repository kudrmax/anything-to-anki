from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import CardPreviewDTO
from backend.application.utils.highlight import highlight_all_forms
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository


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
                    sentence=highlight_all_forms(
                        candidate.context_fragment,
                        candidate.lemma,
                        candidate.surface_form,
                    ),
                    meaning=(
                        highlight_all_forms(
                            candidate.meaning,
                            candidate.lemma,
                            candidate.surface_form,
                        )
                        if candidate.meaning is not None
                        else None
                    ),
                    ipa=candidate.ipa,
                )
            )
        return cards
