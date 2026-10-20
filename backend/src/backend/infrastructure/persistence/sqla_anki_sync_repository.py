from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select, update

from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
from backend.domain.services.decision_rules import BindingRef
from backend.domain.value_objects.card_change import BindingChanged
from backend.domain.value_objects.card_choice import CHOICE_OF_KIND, CardChoice
from backend.infrastructure.persistence.models import AnkiSyncedCardModel
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from sqlalchemy import ColumnElement
    from sqlalchemy.orm import Session

    from backend.domain.ports.change_recorder import ChangeRecorder
    from backend.domain.value_objects.anki_binding import AnkiBinding


class SqlaAnkiSyncRepository(AnkiSyncRepository):
    """SQLAlchemy implementation of AnkiSyncRepository over `anki_synced_cards`."""

    def __init__(self, session: Session, recorder: ChangeRecorder) -> None:
        self._session = session
        self._recorder = recorder

    def bind(self, binding: AnkiBinding) -> None:
        self._session.add(AnkiSyncedCardModel(
            candidate_id=binding.word_id,
            phrase_id=binding.phrase_id,
            anki_note_id=binding.note_id,
            lemma=binding.lemma,
            pos=binding.pos,
            note_kind=binding.note_kind.value,
            card_choice=CHOICE_OF_KIND[binding.note_kind].value,
            learning_since=binding.learning_since,
        ))
        self._session.flush()
        self._recorder.record(BindingChanged(binding.lemma))

    def release(self, phrase_ids: Iterable[int], at: datetime) -> None:
        for chunk in chunks(list(phrase_ids)):
            self._release(AnkiSyncedCardModel.phrase_id.in_(chunk), at)
        self._session.flush()

    def release_rows(self, binding_ids: Iterable[int], at: datetime) -> None:
        for chunk in chunks(list(binding_ids)):
            self._release(AnkiSyncedCardModel.id.in_(chunk), at)
        self._session.flush()

    def _release(self, which: ColumnElement[bool], at: datetime) -> None:
        active = (which, AnkiSyncedCardModel.released_at.is_(None))
        lemmas = set(self._session.scalars(select(AnkiSyncedCardModel.lemma).where(*active)))
        self._session.execute(
            update(AnkiSyncedCardModel).where(*active).values(released_at=at)
        )
        for lemma in lemmas:
            self._recorder.record(BindingChanged(lemma))

    def orphans(self, lemma: str) -> list[BindingRef]:
        rows = self._session.execute(
            select(
                AnkiSyncedCardModel.id,
                AnkiSyncedCardModel.learning_since,
                AnkiSyncedCardModel.card_choice,
            )
            .where(
                func.lower(AnkiSyncedCardModel.lemma) == lemma.lower(),
                AnkiSyncedCardModel.released_at.is_(None),
                or_(
                    AnkiSyncedCardModel.phrase_id.is_(None),
                    AnkiSyncedCardModel.candidate_id.is_(None),
                ),
            )
            .order_by(AnkiSyncedCardModel.id)
        ).all()
        return [
            BindingRef(binding_id, since, CardChoice(choice)) for binding_id, since, choice in rows
        ]
