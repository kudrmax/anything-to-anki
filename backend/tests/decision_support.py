"""Decisions over a real database: the knowledge scope with a fixed clock, the effects and
the use cases built on the decision tables, as the container builds them."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
from backend.application.use_cases.save_cloze import SaveClozeUseCase
from backend.application.utils.decision_effects import DecisionEffects
from backend.application.utils.knowledge_scope import KnowledgeScope
from backend.application.utils.user_vocabulary import UserVocabulary
from backend.domain.ports.clock import Clock
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_anki_sync_repository import SqlaAnkiSyncRepository
from backend.infrastructure.persistence.sqla_candidate_cloze_repository import (
    SqlaCandidateClozeRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_learning_query import SqlaLearningQuery
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from backend.infrastructure.persistence.sqla_word_mark_repository import SqlaWordMarkRepository
from backend.infrastructure.persistence.sqla_word_state_repository import (
    SqlaWordStateRepository,
)

from tests.lock_support import free_lock

if TYPE_CHECKING:
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from sqlalchemy.orm import Session

NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)


class FixedClock(Clock):
    """A clock that stands still at `moment`, and counts how often it is read."""

    def __init__(self, moment: datetime = NOW) -> None:
        self.moment = moment
        self.reads = 0

    def now(self) -> datetime:
        self.reads += 1
        return self.moment


class Decisions:
    """One request over the session: one knowledge scope, its vocabulary and effects.

    `decision_repo` is a mock to assert on; `request()` starts the next
    request, at a later moment if given."""

    def __init__(
        self, session: Session, *, now: datetime = NOW, lock: SourceOperationLock | None = None,
    ) -> None:
        self.session = session
        self.clock = FixedClock(now)
        self.lock = lock or free_lock()
        self.decision_repo = MagicMock()
        self.scope = KnowledgeScope(
            clock=self.clock,
            word_mark_repo=SqlaWordMarkRepository(session, SessionChangeRecorder(session)),
            learning_query=SqlaLearningQuery(session),
        )
        self.vocabulary = UserVocabulary(
            SqlaWordMarkRepository(session, SessionChangeRecorder(session)),
            self.scope,
        )
        self.word_states = SqlaWordStateRepository(session, SessionChangeRecorder(session))
        self.anki_sync = SqlaAnkiSyncRepository(session, SessionChangeRecorder(session))

    def request(self, now: datetime | None = None) -> Decisions:
        later = Decisions(self.session, now=now or self.clock.moment, lock=self.lock)
        later.decision_repo = self.decision_repo
        return later

    def effects(self) -> DecisionEffects:
        return DecisionEffects(
            word_states=self.word_states,
            vocabulary=self.vocabulary,
            decision_repo=self.decision_repo,
            anki_sync=self.anki_sync,
            lock=self.lock,
        )

    def save_cloze(self) -> SaveClozeUseCase:
        return SaveClozeUseCase(
            occurrence_repo=SqlaOccurrenceRepository(
                self.session, SessionChangeRecorder(self.session),
            ),
            candidate_repo=SqlaCandidateRepository(
                self.session, SessionChangeRecorder(self.session),
            ),
            cloze_repo=SqlaCandidateClozeRepository(
                self.session, SessionChangeRecorder(self.session),
            ),
            card_views=MagicMock(),
            decide_phrase=self.decide_phrase(),
            builder=ClozeBuilder(),
            lock=self.lock,
            unit_of_work=SqlaUnitOfWork(self.session, self.scope),
        )

    def decide_phrase(self) -> DecidePhraseUseCase:
        return DecidePhraseUseCase(
            occurrence_repo=SqlaOccurrenceRepository(
                self.session, SessionChangeRecorder(self.session),
            ),
            candidate_repo=SqlaCandidateRepository(
                self.session, SessionChangeRecorder(self.session),
            ),
            word_states=self.word_states,
            vocabulary=self.vocabulary,
            effects=self.effects(),
            lock=self.lock,
            # The tests press; the card the API answers with is read by the API tests.
            card_views=MagicMock(),
            unit_of_work=SqlaUnitOfWork(self.session, self.scope),
        )
