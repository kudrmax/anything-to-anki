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
        media_base_url: str = "/media",
    ) -> None:
        self._candidate_repo = candidate_repo
        self._media_base_url = media_base_url

    def execute(self, source_id: int) -> list[CardPreviewDTO]:
        candidates = self._candidate_repo.get_by_source(source_id)
        learn_candidates = [c for c in candidates if c.status == CandidateStatus.LEARN]

        cards: list[CardPreviewDTO] = []
        for candidate in learn_candidates:
            screenshot_url: str | None = None
            audio_url: str | None = None
            if candidate.screenshot_path:
                filename = candidate.screenshot_path.rsplit("/", 1)[-1]
                screenshot_url = f"{self._media_base_url}/{candidate.source_id}/{filename}"
            if candidate.audio_path:
                filename = candidate.audio_path.rsplit("/", 1)[-1]
                audio_url = f"{self._media_base_url}/{candidate.source_id}/{filename}"

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
                    screenshot_url=screenshot_url,
                    audio_url=audio_url,
                )
            )
        return cards
