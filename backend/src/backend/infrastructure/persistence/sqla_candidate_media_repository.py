from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
from backend.infrastructure.persistence.models import (
    CandidateMediaModel,
    PhraseModel,
    StoredCandidateModel,
)
from backend.infrastructure.persistence.phrase_owners import word_ids_of
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_media import CandidateMedia


class SqlaCandidateMediaRepository(CandidateMediaRepository):
    """SQLAlchemy implementation of CandidateMediaRepository: the media of phrases."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_phrase_id(self, phrase_id: int) -> CandidateMedia | None:
        return self.get_by_phrase_ids([phrase_id]).get(phrase_id)

    def get_by_phrase_ids(self, phrase_ids: list[int]) -> dict[int, CandidateMedia]:
        words = word_ids_of(self._session, phrase_ids)
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

    def clear_missing_file(self, path: str) -> None:
        for column in (CandidateMediaModel.screenshot_path, CandidateMediaModel.audio_path):
            self._session.execute(
                update(CandidateMediaModel).where(column == path).values({column: None})
            )
        self._session.flush()

    def set_timecodes(self, times: Mapping[int, tuple[int, int] | None]) -> None:
        not_made = (
            CandidateMediaModel.screenshot_path.is_(None)
            & CandidateMediaModel.audio_path.is_(None)
        )
        timed = [
            {"phrase_id": phrase_id, "start_ms": time[0], "end_ms": time[1]}
            for phrase_id, time in times.items() if time is not None
        ]
        if timed:
            upsert = sqlite_insert(CandidateMediaModel)
            self._session.execute(
                upsert.on_conflict_do_update(
                    index_elements=[CandidateMediaModel.phrase_id],
                    set_={"start_ms": upsert.excluded.start_ms, "end_ms": upsert.excluded.end_ms},
                    where=not_made,
                ),
                timed,
            )
        untimed = [phrase_id for phrase_id, time in times.items() if time is None]
        for chunk in chunks(untimed):
            self._session.execute(
                update(CandidateMediaModel)
                .where(CandidateMediaModel.phrase_id.in_(chunk), not_made)
                .values(start_ms=None, end_ms=None)
            )
        self._session.flush()

    def get_all_by_source_id(self, source_id: int) -> list[CandidateMedia]:
        """The media of every phrase of the source: all its files."""
        rows = self._session.execute(
            select(CandidateMediaModel, PhraseModel.candidate_id)
            .join(PhraseModel, PhraseModel.id == CandidateMediaModel.phrase_id)
            .join(StoredCandidateModel, StoredCandidateModel.id == PhraseModel.candidate_id)
            .where(StoredCandidateModel.source_id == source_id)
        ).all()
        return [media.to_entity(word_id) for media, word_id in rows]

    def clear_phrase_paths(
        self, phrase_id: int, *, clear_screenshot: bool, clear_audio: bool,
    ) -> None:
        values: dict[str, None] = {}
        if clear_screenshot:
            values["screenshot_path"] = None
        if clear_audio:
            values["audio_path"] = None
        if not values:
            return
        self._session.execute(
            update(CandidateMediaModel)
            .where(CandidateMediaModel.phrase_id == phrase_id)
            .values(**values)
        )
        self._session.flush()
