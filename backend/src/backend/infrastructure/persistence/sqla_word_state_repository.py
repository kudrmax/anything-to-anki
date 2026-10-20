from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, select, update

from backend.domain.ports.word_state_repository import WordStateRepository
from backend.domain.value_objects.card_change import DecisionChanged
from backend.domain.value_objects.card_choice import (
    Binding,
    CardChoice,
    CardState,
    NoteKind,
    WordState,
    decision_status,
)
from backend.infrastructure.persistence.models import (
    AnkiSyncedCardModel,
    PhraseModel,
    StoredCandidateModel,
)
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterator

    from sqlalchemy import ColumnElement
    from sqlalchemy.orm import Session

    from backend.domain.ports.change_recorder import ChangeRecorder


class SqlaWordStateRepository(WordStateRepository):
    """Words as the decision tables see them: one query over words, their phrases and the
    phrases' active bindings."""

    def __init__(self, session: Session, recorder: ChangeRecorder) -> None:
        self._session = session
        self._recorder = recorder
        self._after_save: Callable[[], None] = self._expire

    def _expire(self) -> None:
        """Core updates bypass the ORM: objects the session holds would read the old choice."""
        self._session.expire_all()

    @contextmanager
    def batch(self) -> Iterator[None]:
        self._after_save = _nothing
        try:
            yield
        finally:
            self._after_save = self._expire
            self._expire()

    def of_word(self, word_id: int) -> WordState | None:
        return self._read(StoredCandidateModel.id == word_id).get(word_id)

    def of_source(self, source_id: int) -> dict[int, WordState]:
        return self._read(StoredCandidateModel.source_id == source_id)

    def of_words(self, word_ids: Collection[int]) -> dict[int, WordState]:
        found: dict[int, WordState] = {}
        for chunk in chunks(list(word_ids)):
            found.update(self._read(StoredCandidateModel.id.in_(chunk)))
        return found

    def of_lemma(self, lemma: str) -> list[WordState]:
        return list(self._read(func.lower(StoredCandidateModel.lemma) == lemma.lower()).values())

    def save(self, word: WordState) -> None:
        # A card that stops being the decision is written first: the decision card is unique.
        for card in sorted(word.cards, key=lambda c: c.is_decision):
            self._session.execute(
                update(PhraseModel)
                .where(PhraseModel.id == card.card_id, PhraseModel.candidate_id == word.word_id)
                .values(choice=card.choice.value)
                .execution_options(synchronize_session=False)
            )
        self._session.execute(
            update(StoredCandidateModel)
            .where(StoredCandidateModel.id == word.word_id)
            .values(status=decision_status(word).value)
            .execution_options(synchronize_session=False)
        )
        self._session.flush()
        self._recorder.record(DecisionChanged(word.lemma))
        self._after_save()

    def _read(self, where: ColumnElement[bool]) -> dict[int, WordState]:
        rows = self._session.execute(
            select(
                StoredCandidateModel.id,
                StoredCandidateModel.lemma,
                StoredCandidateModel.pos,
                StoredCandidateModel.source_id,
                PhraseModel.id,
                PhraseModel.choice,
                AnkiSyncedCardModel.note_kind,
                AnkiSyncedCardModel.learning_since,
            )
            .outerjoin(PhraseModel, PhraseModel.candidate_id == StoredCandidateModel.id)
            .outerjoin(
                AnkiSyncedCardModel,
                and_(
                    AnkiSyncedCardModel.phrase_id == PhraseModel.id,
                    AnkiSyncedCardModel.released_at.is_(None),
                ),
            )
            .where(where)
            .order_by(StoredCandidateModel.id, PhraseModel.id)
        ).all()
        facts: dict[int, tuple[str, str, int]] = {}
        cards: dict[int, list[CardState]] = {}
        for word_id, lemma, pos, source_id, phrase_id, choice, kind, since in rows:
            facts[word_id] = (lemma, pos, source_id)
            found = cards.setdefault(word_id, [])
            if phrase_id is not None:
                binding = Binding(NoteKind(kind), since) if kind is not None else None
                found.append(CardState(phrase_id, CardChoice(choice), binding))
        return {
            word_id: WordState(word_id, lemma, pos, source_id, tuple(cards[word_id]))
            for word_id, (lemma, pos, source_id) in facts.items()
        }


def _nothing() -> None:
    return None
