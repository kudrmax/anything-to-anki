from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
from backend.infrastructure.persistence.models import (
    CandidateMediaModel,
    PhraseModel,
    StoredCandidateModel,
)
from backend.infrastructure.persistence.primary_phrase import (
    PrimaryPhrases,
    primary_phrase_id,
    word_is_active,
    words_of_source,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_media import CandidateMedia


class SqlaCandidateMediaRepository(CandidateMediaRepository):
    """SQLAlchemy implementation of CandidateMediaRepository: the media of phrases."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._primary = PrimaryPhrases(session)

    # ── by phrase ──────────────────────────────────────────────────────

    def get_by_phrase_id(self, phrase_id: int) -> CandidateMedia | None:
        return self.get_by_phrase_ids([phrase_id]).get(phrase_id)

    def get_by_phrase_ids(self, phrase_ids: list[int]) -> dict[int, CandidateMedia]:
        words = self._primary.word_ids(phrase_ids)
        if not words:
            return {}
        rows = self._session.scalars(
            select(CandidateMediaModel).where(CandidateMediaModel.phrase_id.in_(list(words)))
        )
        return {row.phrase_id: row.to_entity(words[row.phrase_id]) for row in rows}

    def upsert_for_phrase(self, phrase_id: int, media: CandidateMedia) -> None:
        existing = self._session.get(CandidateMediaModel, phrase_id)
        if existing is None:
            self._session.add(CandidateMediaModel.from_entity(phrase_id, media))
        else:
            existing.screenshot_path = media.screenshot_path
            existing.audio_path = media.audio_path
            existing.start_ms = media.start_ms
            existing.end_ms = media.end_ms
            existing.generated_at = media.generated_at
        self._session.flush()

    # ── by word, through its primary phrase ────────────────────────────
    # TRANSITIONAL(words-phrases): removed in Task 10

    def get_by_candidate_id(self, candidate_id: int) -> CandidateMedia | None:
        return self.get_by_candidate_ids([candidate_id]).get(candidate_id)

    def get_all_by_source(self, source_id: int) -> dict[int, CandidateMedia]:
        return self.get_by_candidate_ids(words_of_source(self._session, source_id))

    def get_all_by_source_id(self, source_id: int) -> list[CandidateMedia]:
        """The media of every phrase of the source, not only of primary ones: all the files."""
        rows = self._session.execute(
            select(CandidateMediaModel, PhraseModel.candidate_id)
            .join(PhraseModel, PhraseModel.id == CandidateMediaModel.phrase_id)
            .join(StoredCandidateModel, StoredCandidateModel.id == PhraseModel.candidate_id)
            .where(StoredCandidateModel.source_id == source_id)
        ).all()
        return [media.to_entity(word_id) for media, word_id in rows]

    def get_by_candidate_ids(self, candidate_ids: list[int]) -> dict[int, CandidateMedia]:
        primaries = self._primary.ids(candidate_ids)
        by_phrase = self.get_by_phrase_ids(list(primaries.values()))
        return {
            word_id: by_phrase[phrase_id]
            for word_id, phrase_id in primaries.items()
            if phrase_id in by_phrase
        }

    def upsert(self, media: CandidateMedia) -> None:
        phrase_id = self._primary.id(media.candidate_id)
        if phrase_id is not None:
            self.upsert_for_phrase(phrase_id, media)

    def clear_paths(
        self,
        candidate_id: int,
        *,
        clear_screenshot: bool,
        clear_audio: bool,
    ) -> None:
        values: dict[str, None] = {}
        if clear_screenshot:
            values["screenshot_path"] = None
        if clear_audio:
            values["audio_path"] = None
        phrase_id = self._primary.id(candidate_id)
        if not values or phrase_id is None:
            return
        self._session.execute(
            update(CandidateMediaModel)
            .where(CandidateMediaModel.phrase_id == phrase_id)
            .values(**values)
        )
        self._session.flush()

    def get_eligible_candidate_ids(
        self,
        source_id: int,
    ) -> list[int]:
        stmt = (
            select(StoredCandidateModel.id)
            .join(PhraseModel, PhraseModel.id == primary_phrase_id(StoredCandidateModel.id))
            .join(CandidateMediaModel, CandidateMediaModel.phrase_id == PhraseModel.id)
            .where(
                StoredCandidateModel.source_id == source_id,
                word_is_active(),
                CandidateMediaModel.start_ms.is_not(None),
                CandidateMediaModel.end_ms.is_not(None),
                CandidateMediaModel.screenshot_path.is_(None),
            )
        )
        return [row[0] for row in self._session.execute(stmt).all()]
