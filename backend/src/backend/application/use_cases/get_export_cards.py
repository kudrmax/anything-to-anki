from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import CardPreviewDTO, ExportSectionDTO, GlobalExportDTO
from backend.application.utils.highlight import highlight_all_forms, highlight_target, line_breaks
from backend.domain.services.export_readiness import missing_parts
from backend.domain.value_objects.export_group import ExportGroup
from backend.domain.value_objects.source_scope import ScopeKind

if TYPE_CHECKING:
    from backend.application.utils.export_queue import ExportBatch, ExportCard, ExportQueue
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.services.cloze_builder import ClozeBuilder
    from backend.domain.value_objects.source_scope import SourceScope


class GetExportCardsUseCase:
    """Builds card previews for 'learn' words not yet exported, each by the phrase of its
    decision: ready and incomplete apart."""

    def __init__(
        self,
        export_queue: ExportQueue,
        source_repo: SourceRepository,
        cloze_builder: ClozeBuilder,
        scope_resolver: SourceScopeResolver,
        media_base_url: str = "/media",
    ) -> None:
        self._export_queue = export_queue
        self._source_repo = source_repo
        self._cloze_builder = cloze_builder
        self._scope_resolver = scope_resolver
        self._media_base_url = media_base_url

    def execute(self, scope: SourceScope) -> GlobalExportDTO:
        """The export of a set of sources: one source, a collection, Unsorted or all."""
        if scope.kind is ScopeKind.ALL:
            batch = self._export_queue.for_all()
        else:
            ids = {s.id for s in self._scope_resolver.sources(scope) if s.id is not None}
            batch = self._export_queue.for_sources(ids)
        return self._build(batch).model_copy(update={"title": self._scope_resolver.title(scope)})

    def _build(self, batch: ExportBatch) -> GlobalExportDTO:
        return GlobalExportDTO(
            ready=self._build_sections(batch.in_group(ExportGroup.READY)),
            incomplete=self._build_sections(batch.in_group(ExportGroup.INCOMPLETE)),
            exported_count=batch.exported_count,
        )

    def _build_sections(self, cards: list[ExportCard]) -> list[ExportSectionDTO]:
        sections: list[ExportSectionDTO] = []
        for src_id, group in groupby(cards, key=lambda c: c.word.source_id):
            source = self._source_repo.get_by_id(src_id)
            sections.append(ExportSectionDTO(
                source_id=src_id,
                source_title=source.title if source and source.title else f"Source #{src_id}",
                cards=[self._build_card(c) for c in group],
            ))
        return sections

    def _build_card(self, card: ExportCard) -> CardPreviewDTO:
        candidate = card.word
        decision = card.phrase
        screenshot_url: str | None = None
        audio_url: str | None = None
        if decision.media and decision.media.screenshot_path:
            filename = decision.media.screenshot_path.rsplit("/", 1)[-1]
            screenshot_url = f"{self._media_base_url}/{candidate.source_id}/{filename}"
        if decision.media and decision.media.audio_path:
            filename = decision.media.audio_path.rsplit("/", 1)[-1]
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
        if decision.tts and decision.tts.audio_path:
            filename = decision.tts.audio_path.rsplit("/", 1)[-1]
            tts_audio_url = f"{self._media_base_url}/{candidate.source_id}/{filename}"

        meaning_obj = decision.meaning
        meaning_text = meaning_obj.meaning if meaning_obj else None
        ipa_text = meaning_obj.ipa if meaning_obj else None
        translation_text = meaning_obj.translation if meaning_obj else None
        synonyms_text = meaning_obj.synonyms if meaning_obj else None
        examples_text = meaning_obj.examples if meaning_obj else None

        phrase = decision.phrase
        cloze = card.cloze_markup(self._cloze_builder)
        sentence = (
            highlight_target(phrase)
            if cloze is None
            else line_breaks(
                self._cloze_builder.highlight_hidden(phrase, cloze.hidden_word_indices),
            )
        )

        return CardPreviewDTO(
            candidate_id=card.word_id,
            phrase_id=card.phrase_id,
            lemma=candidate.lemma,
            sentence=sentence,
            meaning=(
                highlight_all_forms(meaning_text, candidate.lemma, phrase.target_text())
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
            missing=[part.value for part in missing_parts(decision)],
            is_cloze=cloze is not None,
        )
