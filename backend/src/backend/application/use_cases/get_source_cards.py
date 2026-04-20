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
            if candidate.media and candidate.media.screenshot_path:
                filename = candidate.media.screenshot_path.rsplit("/", 1)[-1]
                screenshot_url = f"{self._media_base_url}/{candidate.source_id}/{filename}"
            if candidate.media and candidate.media.audio_path:
                filename = candidate.media.audio_path.rsplit("/", 1)[-1]
                audio_url = f"{self._media_base_url}/{candidate.source_id}/{filename}"

            pronunciation_us_url: str | None = None
            pronunciation_uk_url: str | None = None
            if candidate.pronunciation and candidate.pronunciation.us_audio_path:
                filename = candidate.pronunciation.us_audio_path.rsplit("/", 1)[-1]
                pronunciation_us_url = f"{self._media_base_url}/{candidate.source_id}/{filename}"
            if candidate.pronunciation and candidate.pronunciation.uk_audio_path:
                filename = candidate.pronunciation.uk_audio_path.rsplit("/", 1)[-1]
                pronunciation_uk_url = f"{self._media_base_url}/{candidate.source_id}/{filename}"

            meaning_obj = candidate.meaning
            meaning_text = meaning_obj.meaning if meaning_obj else None
            ipa_text = meaning_obj.ipa if meaning_obj else None
            translation_text = meaning_obj.translation if meaning_obj else None
            synonyms_text = meaning_obj.synonyms if meaning_obj else None
            examples_text = meaning_obj.examples if meaning_obj else None

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
                            meaning_text,
                            candidate.lemma,
                            candidate.surface_form,
                        )
                        if meaning_text is not None
                        else None
                    ),
                    translation=translation_text,
                    synonyms=synonyms_text,
                    examples=examples_text,
                    ipa=ipa_text,
                    screenshot_url=screenshot_url,
                    audio_url=audio_url,
                    pronunciation_us_url=pronunciation_us_url,
                    pronunciation_uk_url=pronunciation_uk_url,
                )
            )
        return cards
