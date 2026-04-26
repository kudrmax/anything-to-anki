from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from backend.domain.ports.enrichment_cache_repository import EnrichmentCacheRepository
from backend.infrastructure.persistence.models import (
    CandidateMeaningModel,
    CandidateMediaModel,
    CandidatePronunciationModel,
    CandidateTTSModel,
    EnrichmentCacheModel,
    StoredCandidateModel,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SqlaEnrichmentCacheRepository(EnrichmentCacheRepository):
    """SQLAlchemy implementation of EnrichmentCacheRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_from_source(self, source_id: int) -> None:
        stmt = (
            select(
                StoredCandidateModel.source_id,
                StoredCandidateModel.lemma,
                StoredCandidateModel.pos,
                StoredCandidateModel.context_fragment,
                # meaning
                CandidateMeaningModel.meaning,
                CandidateMeaningModel.translation,
                CandidateMeaningModel.synonyms,
                CandidateMeaningModel.examples,
                CandidateMeaningModel.ipa,
                CandidateMeaningModel.generated_at.label("meaning_generated_at"),
                # media
                CandidateMediaModel.screenshot_path,
                CandidateMediaModel.audio_path,
                CandidateMediaModel.start_ms,
                CandidateMediaModel.end_ms,
                CandidateMediaModel.generated_at.label("media_generated_at"),
                # pronunciation
                CandidatePronunciationModel.us_audio_path,
                CandidatePronunciationModel.uk_audio_path,
                CandidatePronunciationModel.generated_at.label("pronunciation_generated_at"),
                # tts
                CandidateTTSModel.audio_path.label("tts_audio_path"),
                CandidateTTSModel.generated_at.label("tts_generated_at"),
            )
            .outerjoin(
                CandidateMeaningModel,
                CandidateMeaningModel.candidate_id == StoredCandidateModel.id,
            )
            .outerjoin(
                CandidateMediaModel,
                CandidateMediaModel.candidate_id == StoredCandidateModel.id,
            )
            .outerjoin(
                CandidatePronunciationModel,
                CandidatePronunciationModel.candidate_id == StoredCandidateModel.id,
            )
            .outerjoin(
                CandidateTTSModel,
                CandidateTTSModel.candidate_id == StoredCandidateModel.id,
            )
            .where(StoredCandidateModel.source_id == source_id)
        )
        rows = self._session.execute(stmt).all()

        for row in rows:
            cache_entry = EnrichmentCacheModel(
                source_id=row.source_id,
                lemma=row.lemma,
                pos=row.pos,
                context_fragment=row.context_fragment,
                meaning=row.meaning,
                translation=row.translation,
                synonyms=row.synonyms,
                examples=row.examples,
                ipa=row.ipa,
                meaning_generated_at=row.meaning_generated_at,
                screenshot_path=row.screenshot_path,
                audio_path=row.audio_path,
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                media_generated_at=row.media_generated_at,
                us_audio_path=row.us_audio_path,
                uk_audio_path=row.uk_audio_path,
                pronunciation_generated_at=row.pronunciation_generated_at,
                tts_audio_path=row.tts_audio_path,
                tts_generated_at=row.tts_generated_at,
            )
            self._session.merge(cache_entry)
        self._session.flush()
        logger.info("enrichment cache: saved %d rows (source_id=%d)", len(rows), source_id)

    def restore_to_candidates(self, source_id: int) -> int:
        stmt = (
            select(
                StoredCandidateModel.id.label("candidate_id"),
                EnrichmentCacheModel,
            )
            .join(
                EnrichmentCacheModel,
                (EnrichmentCacheModel.source_id == StoredCandidateModel.source_id)
                & (EnrichmentCacheModel.lemma == StoredCandidateModel.lemma)
                & (EnrichmentCacheModel.pos == StoredCandidateModel.pos)
                & (
                    EnrichmentCacheModel.context_fragment
                    == StoredCandidateModel.context_fragment
                ),
            )
            .where(StoredCandidateModel.source_id == source_id)
        )
        rows = self._session.execute(stmt).all()

        restored = 0
        for row in rows:
            cid: int = row.candidate_id
            cache: EnrichmentCacheModel = row.EnrichmentCacheModel
            any_restored = False

            if cache.meaning is not None:
                self._session.merge(
                    CandidateMeaningModel(
                        candidate_id=cid,
                        meaning=cache.meaning,
                        translation=cache.translation,
                        synonyms=cache.synonyms,
                        examples=cache.examples,
                        ipa=cache.ipa,
                        generated_at=cache.meaning_generated_at,
                    )
                )
                any_restored = True

            if cache.screenshot_path is not None or cache.audio_path is not None:
                self._session.merge(
                    CandidateMediaModel(
                        candidate_id=cid,
                        screenshot_path=cache.screenshot_path,
                        audio_path=cache.audio_path,
                        start_ms=cache.start_ms,
                        end_ms=cache.end_ms,
                        generated_at=cache.media_generated_at,
                    )
                )
                any_restored = True

            if cache.us_audio_path is not None or cache.uk_audio_path is not None:
                self._session.merge(
                    CandidatePronunciationModel(
                        candidate_id=cid,
                        us_audio_path=cache.us_audio_path,
                        uk_audio_path=cache.uk_audio_path,
                        generated_at=cache.pronunciation_generated_at,
                    )
                )
                any_restored = True

            if cache.tts_audio_path is not None:
                self._session.merge(
                    CandidateTTSModel(
                        candidate_id=cid,
                        audio_path=cache.tts_audio_path,
                        generated_at=cache.tts_generated_at,
                    )
                )
                any_restored = True

            if any_restored:
                restored += 1

        self._session.flush()
        logger.info(
            "enrichment cache: restored %d/%d candidates (source_id=%d)",
            restored,
            len(rows),
            source_id,
        )
        return restored

    def cleanup(self, source_id: int) -> None:
        self._session.execute(
            delete(EnrichmentCacheModel).where(
                EnrichmentCacheModel.source_id == source_id
            )
        )
        self._session.flush()

    def cleanup_all(self) -> None:
        self._session.execute(delete(EnrichmentCacheModel))
        self._session.flush()
