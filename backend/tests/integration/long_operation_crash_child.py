"""Run by test_long_operation_crash in a process of its own: processes the given sources as
a long operation on the database file, and at `stop_at` — the analysis of the last source,
or the apply of the last source inside the operation's write — tells the test it is there by
writing `marker`, then waits to be killed."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from backend.application.utils.source_rebuilder import SourceRebuilder
from backend.domain.value_objects.long_operation_kind import LongOperationKind
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import create_session_factory

WAIT_TO_BE_KILLED_S = 120


def main() -> None:
    db, stop_at, marker, *raw_ids = sys.argv[1:]
    source_ids = [int(i) for i in raw_ids]
    method = {"analyse": "analyse", "apply": "apply_inside"}[stop_at]
    original = getattr(SourceRebuilder, method)
    calls = {"n": 0}

    def stop_on_the_last(self: SourceRebuilder, *args: object, **kwargs: object) -> object:
        calls["n"] += 1
        result = original(self, *args, **kwargs)
        if calls["n"] == len(source_ids):
            Path(marker).write_text("here")
            time.sleep(WAIT_TO_BE_KILLED_S)
        return result

    setattr(SourceRebuilder, method, stop_on_the_last)
    factory = create_session_factory(f"sqlite:///{db}")
    container = Container(session_factory=factory)

    def run() -> None:
        with factory() as session:
            container.process_source_use_case(session).run(source_ids)

    Container._spawn_long_operation = lambda _self, work: work()  # type: ignore[method-assign]
    with factory() as session:
        container.long_operation_launcher(session).start(LongOperationKind.PROCESS, run)


if __name__ == "__main__":
    main()
