from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from backend.domain.exceptions import LongOperationInProgressError
from backend.infrastructure.persistence.sqla_long_operation_lock import SqlaLongOperationLock

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# How long a waiting write sleeps before it looks at the lock again.
GATE_RETRY_SECONDS = 0.5


class WriteGate(ABC):
    """Decides, inside a just-begun write transaction, whether the write may go on while a
    level change holds its lock. Each process is built with the gate of its role."""

    @abstractmethod
    def admit(self, session: Session) -> bool:
        """True: go on. False: roll back, `wait`, begin again. Raising refuses the write."""

    def wait(self) -> None:
        time.sleep(GATE_RETRY_SECONDS)


class RefuseDuringLongOperation(WriteGate):
    """A request: refused at once, the user sees the level change instead."""

    def admit(self, session: Session) -> bool:
        if SqlaLongOperationLock(session).held():
            raise LongOperationInProgressError
        return True


class WaitOutLongOperation(WriteGate):
    """The worker: its write lands once the level change is over. `waited_seconds` is the
    total time spent waiting, so a job's timeout can leave it out."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._waited = 0.0

    def admit(self, session: Session) -> bool:
        return not SqlaLongOperationLock(session).held()

    def wait(self) -> None:
        started = time.monotonic()
        super().wait()
        with self._lock:
            self._waited += time.monotonic() - started

    def waited_seconds(self) -> float:
        with self._lock:
            return self._waited


class OwnLongOperation(WriteGate):
    """The level change itself: its lock is what keeps the others out."""

    def admit(self, session: Session) -> bool:
        return True
