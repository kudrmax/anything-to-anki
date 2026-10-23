"""A level change applies the new settings and «Find words again» of every source in one
write: all of it or none of it."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from backend.application.dto.long_operation_dtos import LongOperationOutcome
from backend.application.dto.settings_dtos import UpdateSettingsRequest
from backend.application.use_cases.change_level import ChangeLevelUseCase
from backend.application.use_cases.start_level_change import StartLevelChangeUseCase
from backend.application.utils.long_operation_progress import LongOperationProgress
from backend.application.utils.settings_writer import SettingsWriter
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.exceptions import (
    LongOperationInProgressError,
    LongOperationRunningError,
    SourceOperationBusyError,
)
from backend.domain.ports.running_operations import RunningOperations
from backend.domain.services.long_operation_progress import DONE_PERCENT
from backend.domain.value_objects.long_operation_kind import LongOperationKind
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_collection_repository import (
    SqlaCollectionRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_long_operation_lock import SqlaLongOperationLock
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from backend.infrastructure.persistence.write_gate import OwnLongOperation
from sqlalchemy import text

from tests.candidate_sorter_support import threshold_resolver
from tests.source_order_support import added_order
from tests.source_rebuild_support import SOURCE, Bench, at, document, word

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.application.utils.source_rebuilder import SourceRebuilder
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

OTHER_SOURCE = 2
OLD_SECTION = "extra"
NEW_SECTION = "ready"
NEW_LEVEL = "C1"
TO_C1 = UpdateSettingsRequest(cefr_level=NEW_LEVEL, anki_deck_name="Deck after")


class _Running(RunningOperations):
    def __init__(self) -> None:
        self.long_operation = False

    def any_running(self) -> bool:
        return self.long_operation


class World:
    """Two processed sources whose phrases sit in a section the next rebuild moves."""

    def __init__(self, session: Session) -> None:
        self.bench = Bench(session)
        self.session = session
        session.execute(text(
            "INSERT INTO sources (id, title, status, role, created_at)"
            " VALUES (:id, 'other', 'new', 'content', '2026-01-01 00:00:00')"
        ), {"id": OTHER_SOURCE})
        SqlaDocumentRepository(session).save(OTHER_SOURCE, document())
        session.commit()
        self.bench.analysis = [word("glare", at(0), at(1))]
        for source_id in (SOURCE, OTHER_SOURCE):
            process = self.bench.process()
            process.start(source_id)
            session.commit()
            process.execute(source_id)
        session.execute(text(f"UPDATE phrases SET earned_section = '{OLD_SECTION}'"))
        session.commit()
        self.settings = SqlaSettingsRepository(session, SessionChangeRecorder(session))
        self.lock = SqlaLongOperationLock(session)
        self.progress = LongOperationProgress()
        self.rebuilder: SourceRebuilder = self.bench.rebuilder()
        self.running = _Running()

    def start(self) -> None:
        self.progress.try_start(LongOperationKind.LEVEL_CHANGE)
        StartLevelChangeUseCase(
            source_lock=self.bench.lock,
            level_change_lock=self.lock,
            unit_of_work=SqlaUnitOfWork(self.session, self.bench.vocabulary.scope),
            running=self.running,
        ).execute()

    def change(self, request: UpdateSettingsRequest = TO_C1) -> None:
        self.start()
        ChangeLevelUseCase(
            settings_writer=SettingsWriter(self.settings),
            threshold_resolver=threshold_resolver(self.settings),
            scope_resolver=SourceScopeResolver(
                self.bench.sources, SqlaCollectionRepository(self.session), added_order(),
            ),
            rebuilder=self.rebuilder,
            lock=self.lock,
            media_files=self.bench.media_files,
            unit_of_work=SqlaUnitOfWork(
                self.session, self.bench.vocabulary.scope, gate=OwnLongOperation(),
            ),
            progress=self.progress,
        ).execute(request)

    def sections(self) -> set[str | None]:
        self.session.expire_all()
        return {row[0] for row in self.session.execute(text("SELECT earned_section FROM phrases"))}

    def setting(self, key: str) -> str | None:
        self.session.expire_all()
        return self.settings.get(key)

    def unchanged(self) -> bool:
        return (
            self.sections() == {OLD_SECTION}
            and self.setting("cefr_level") is None
            and self.setting("anki_deck_name") is None
            and not self.lock.held()
        )


@pytest.fixture
def world(db_session: Session) -> World:
    return World(db_session)


def _on_call(target: object, name: str, nth: int, effect: Callable[[], None]) -> object:
    """`target.name` with `effect` run at its `nth` call (1-based), before the call itself."""
    original = getattr(target, name)
    calls = 0

    def wrapped(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == nth:
            effect()
        return original(*args, **kwargs)

    return patch.object(target, name, wrapped)


def test_success_applies_level_settings_and_every_source(world: World) -> None:
    world.change()

    assert world.setting("cefr_level") == NEW_LEVEL
    assert world.setting("anki_deck_name") == "Deck after"
    assert world.sections() == {NEW_SECTION}
    assert not world.lock.held()
    status = world.progress.status()
    assert (status.running, status.outcome, status.percent) == (
        False, LongOperationOutcome.SUCCEEDED, DONE_PERCENT,
    )


def test_failure_on_second_source_changes_nothing(world: World) -> None:
    def boom() -> None:
        raise RuntimeError("second source broke")

    with _on_call(world.rebuilder, "apply_inside", 2, boom):  # type: ignore[attr-defined]
        world.change()

    assert world.unchanged()
    status = world.progress.status()
    assert (status.outcome, status.error) == (LongOperationOutcome.FAILED, "second source broke")


def test_cancel_in_analyse_writes_nothing(world: World) -> None:
    with _on_call(world.rebuilder, "analyse", 1, world.progress.cancel):  # type: ignore[attr-defined]
        world.change()

    assert world.unchanged()
    assert world.progress.status().outcome is LongOperationOutcome.CANCELLED


def test_cancel_in_apply_rolls_back(world: World) -> None:
    with _on_call(world.rebuilder, "apply_inside", 1, world.progress.cancel):  # type: ignore[attr-defined]
        world.change()

    assert world.unchanged()
    assert world.progress.status().outcome is LongOperationOutcome.CANCELLED


def test_cannot_cancel_in_finish(world: World) -> None:
    refused: list[bool] = []

    with _on_call(world.lock, "release", 1, lambda: refused.append(world.progress.cancel())):  # type: ignore[attr-defined]
        world.change()

    assert refused == [False]
    assert world.progress.status().outcome is LongOperationOutcome.SUCCEEDED
    assert world.setting("cefr_level") == NEW_LEVEL


def test_start_refused_when_source_busy(world: World) -> None:
    assert world.bench.lock.acquire(SOURCE, SourceOperationKind.PROCESS)
    world.session.commit()

    with pytest.raises(SourceOperationBusyError):
        world.start()

    assert not world.lock.held()


def test_start_refused_when_locked(world: World) -> None:
    world.start()

    with pytest.raises(LongOperationInProgressError):
        world.start()


def test_threshold_only_change_goes_the_same_way(world: World) -> None:
    world.change(UpdateSettingsRequest(frequent_word_threshold="5.0"))

    requests = [call.args[1] for call in world.bench.analyze_text.execute.call_args_list]
    assert requests[-1].frequent_word_zipf == 5.0
    assert world.setting("frequent_word_threshold") == "5.0"
    assert world.sections() == {NEW_SECTION}


def test_percent_never_goes_back(world: World) -> None:
    seen: list[int] = []

    def record() -> None:
        seen.append(world.progress.status().percent)

    with (
        _on_call(world.rebuilder, "analyse", 1, record),  # type: ignore[attr-defined]
        _on_call(world.rebuilder, "apply_inside", 1, record),  # type: ignore[attr-defined]
        _on_call(world.lock, "release", 1, record),  # type: ignore[attr-defined]
    ):
        world.change()
    seen.append(world.progress.status().percent)

    assert seen == sorted(seen)
    assert seen[-1] == DONE_PERCENT
    assert len(set(seen)) == len(seen)


def test_source_without_text_has_sections_moved_only(db_session: Session) -> None:
    bench = Bench(db_session, role="topic", status="done")
    settings = SqlaSettingsRepository(db_session, SessionChangeRecorder(db_session))
    lock = SqlaLongOperationLock(db_session)
    progress = LongOperationProgress()
    progress.try_start(LongOperationKind.LEVEL_CHANGE)
    lock.take()
    db_session.commit()

    ChangeLevelUseCase(
        settings_writer=SettingsWriter(settings),
        threshold_resolver=threshold_resolver(settings),
        scope_resolver=SourceScopeResolver(
            bench.sources, SqlaCollectionRepository(db_session), added_order(),
        ),
        rebuilder=bench.rebuilder(),
        lock=lock,
        media_files=bench.media_files,
        unit_of_work=SqlaUnitOfWork(db_session, bench.vocabulary.scope, gate=OwnLongOperation()),
        progress=progress,
    ).execute(TO_C1)

    bench.analyze_text.execute.assert_not_called()
    assert progress.status().outcome is LongOperationOutcome.SUCCEEDED


def test_a_source_that_failed_processing_is_left_out(world: World) -> None:
    """Its analysis fails every time; the change goes on without it, as Find words again
    of all sources did. Update of that source applies the new level once it is fixed."""
    world.session.execute(text("UPDATE sources SET status = 'error' WHERE id = :id"), {
        "id": OTHER_SOURCE,
    })
    world.session.execute(text("DELETE FROM source_documents WHERE source_id = :id"), {
        "id": OTHER_SOURCE,
    })
    world.session.commit()

    world.change()

    assert world.progress.status().outcome is LongOperationOutcome.SUCCEEDED
    assert world.setting("cefr_level") == NEW_LEVEL


def test_a_done_source_without_its_document_fails_the_whole_change(world: World) -> None:
    world.session.execute(text("DELETE FROM source_documents WHERE source_id = :id"), {
        "id": OTHER_SOURCE,
    })
    world.session.commit()

    world.change()

    assert world.unchanged()
    assert world.progress.status().outcome is LongOperationOutcome.FAILED


def test_files_that_cannot_be_removed_do_not_undo_a_committed_change(world: World) -> None:
    def refuse(_paths: object) -> None:
        raise PermissionError("media folder is read-only")

    with patch.object(world.bench.media_files, "remove", refuse):
        world.change()

    assert world.progress.status().outcome is LongOperationOutcome.SUCCEEDED
    assert world.setting("cefr_level") == NEW_LEVEL


def test_start_refused_while_a_long_operation_runs(world: World) -> None:
    """Update of a set takes its sources one by one; a change started between two of them
    would cut it off."""
    world.running.long_operation = True

    with pytest.raises(LongOperationRunningError):
        world.start()

    assert not world.lock.held()
