from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import CardPreviewDTO, ExportSectionDTO, GlobalExportDTO
from backend.application.utils.highlight import highlight_all_forms
from backend.domain.services.export_readiness import missing_parts
from backend.domain.value_objects.export_group import ExportGroup

if TYPE_CHECKING:
    from backend.application.utils.export_queue import ExportBatch, ExportQueue
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.source_repository import SourceRepository


class GetExportCardsUseCase:
    """Builds card previews for 'learn' candidates not yet exported: ready and incomplete apart."""

    def __init__(
        self,
        export_queue: ExportQueue,
        source_repo: SourceRepository,
        media_base_url: str = "/media",
    ) -> None:
        self._export_queue = export_queue
        self._source_repo = source_repo
        self._media_base_url = media_base_url

    def execute(self, source_id: int) -> GlobalExportDTO:
        return self._build(self._export_queue.for_source(source_id))

    def execute_all(self) -> GlobalExportDTO:
        return self._build(self._export_queue.for_all())

    def _build(self, batch: ExportBatch) -> GlobalExportDTO:
        return GlobalExportDTO(
            ready=self._build_sections(batch.in_group(ExportGroup.READY)),
            incomplete=self._build_sections(batch.in_group(ExportGroup.INCOMPLETE)),
            exported_count=batch.exported_count,
        )

    def _build_sections(self, candidates: list[StoredCandidate]) -> list[ExportSectionDTO]:
        sections: list[ExportSectionDTO] = []
        for src_id, group in groupby(candidates, key=lambda c: c.source_id):
            source = self._source_repo.get_by_id(src_id)
            sections.append(ExportSectionDTO(
                source_id=src_id,
                source_title=source.title if source and source.title else f"Source #{src_id}",
                cards=[self._build_card(c) for c in group],
            ))
        return sections

    def _build_card(self, candidate: StoredCandidate) -> CardPreviewDTO:
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

        tts_audio_url: str | None = None
        if candidate.tts and candidate.tts.audio_path:
            filename = candidate.tts.audio_path.rsplit("/", 1)[-1]
            tts_audio_url = f"{self._media_base_url}/{candidate.source_id}/{filename}"

        meaning_obj = candidate.meaning
        meaning_text = meaning_obj.meaning if meaning_obj else None
        ipa_text = meaning_obj.ipa if meaning_obj else None
        translation_text = meaning_obj.translation if meaning_obj else None
        synonyms_text = meaning_obj.synonyms if meaning_obj else None
        examples_text = meaning_obj.examples if meaning_obj else None

        return CardPreviewDTO(
            candidate_id=candidate.id,  # type: ignore[arg-type]
            lemma=candidate.lemma,
            sentence=highlight_all_forms(
                candidate.card_phrase,
                candidate.lemma,
                candidate.surface_form,
            ),
            meaning=(
                highlight_all_forms(meaning_text, candidate.lemma, candidate.surface_form)
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
            tts_audio_url=tts_audio_url,
            missing=[part.value for part in missing_parts(candidate)],
        )
