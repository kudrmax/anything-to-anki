"""Decisions over a real database: the knowledge scope with a fixed clock, the effects and
the use cases built on the decision tables, as the container builds them."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
from backend.application.utils.decided_elsewhere import DecidedElsewhere
from backend.application.utils.decision_effects import DecisionEffects
from backend.application.utils.knowledge_scope import KnowledgeScope
from backend.application.utils.user_vocabulary import UserVocabulary
from backend.domain.ports.clock import Clock
from backend.infrastructure.persistence.sqla_anki_sync_repository import SqlaAnkiSyncRepository
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_known_word_repository import SqlaKnownWordRepository
from backend.infrastructure.persistence.sqla_learning_query import SqlaLearningQuery
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_unknown_word_repository import (
    SqlaUnknownWordRepository,
)
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

    `review_status` and `decision_repo` are mocks to assert on; `request()` starts the next
    request, at a later moment if given."""

    def __init__(
        self, session: Session, *, now: datetime = NOW, lock: SourceOperationLock | None = None,
    ) -> None:
        self.session = session
        self.clock = FixedClock(now)
        self.lock = lock or free_lock()
        self.review_status = MagicMock()
        self.decision_repo = MagicMock()
        self.scope = KnowledgeScope(
            clock=self.clock,
            known_word_repo=SqlaKnownWordRepository(session),
            unknown_word_repo=SqlaUnknownWordRepository(session),
            learning_query=SqlaLearningQuery(session),
        )
        self.vocabulary = UserVocabulary(
            SqlaKnownWordRepository(session), SqlaUnknownWordRepository(session), self.scope,
        )
        self.word_states = SqlaWordStateRepository(session)
        self.anki_sync = SqlaAnkiSyncRepository(session)

    def request(self, now: datetime | None = None) -> Decisions:
        later = Decisions(self.session, now=now or self.clock.moment, lock=self.lock)
        later.review_status = self.review_status
        later.decision_repo = self.decision_repo
        return later

    def effects(self) -> DecisionEffects:
        return DecisionEffects(
            word_states=self.word_states,
            vocabulary=self.vocabulary,
            decision_repo=self.decision_repo,
            anki_sync=self.anki_sync,
            review_status=self.review_status,
            lock=self.lock,
        )

    def decide_phrase(self) -> DecidePhraseUseCase:
        return DecidePhraseUseCase(
            occurrence_repo=SqlaOccurrenceRepository(self.session),
            candidate_repo=SqlaCandidateRepository(self.session),
            word_states=self.word_states,
            vocabulary=self.vocabulary,
            decided_elsewhere=DecidedElsewhere(self.vocabulary),
            effects=self.effects(),
            lock=self.lock,
        )
