# Atomic level change — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Saving a new level (or frequent-word threshold) applies settings + «Find words again» of every source + card states in one transaction, behind an app-wide write lock, with a percent loader and Cancel.

**Architecture:** A lock row in the database, checked by `SqlaUnitOfWork.write()` through a `WriteGate` chosen per process (API refuses, worker waits, the level change itself owns). The change runs on an API-process thread: stage 1 analyses every source with the new values outside any transaction, stage 2 applies all of it in one write that also drops the lock row. Progress and Cancel live in memory of the API process; any frontend polls them.

**Tech Stack:** Python 3.12, SQLAlchemy, SQLite (WAL), FastAPI, Alembic; React + TS (Vite).

**Spec:** `internal/specs/atomic-level-change.md`

## Global Constraints

- Commands only through `make` (`make test`, `make lint`, `make typecheck`); frontend: `npm run lint`, `npm run build`, `npx vitest run`.
- `mypy --strict`; no `Any` without a comment; pydantic for DTO, frozen dataclass for domain.
- DDL only through Alembic; new migration `0061_level_change_lock.py` (re-check the number against all branches before merge).
- Commit messages: conventional, no Claude attribution.
- Every API write refused during a change answers **423**, one code for all.

## Review Focus

1. Worker job running when the change starts → its result write waits, the job is not FAILED by `JOB_TIMEOUT` (Task 3 test).
2. Save pressed twice / from two tabs → second answers 409, one change runs (Task 6 test).
3. Change fails on source N (exception in `apply`) → settings, phrases, card states all as before; lock released; status `failed` (Task 5 test).
4. API restarted mid-change → after startup no lock, old level (Task 1 test for release; manual `kill -9` in Task 8).
5. Source with no text of its own (topic) and source whose document is missing → stage 1 handles them as `rebuild_all` did (sections only / error → whole change fails) (Task 5 test).

---

### Task 1: Lock row

**Files:**
- Create: `backend/src/backend/alembic/versions/0061_level_change_lock.py` — table `level_change_lock(id INTEGER PK CHECK(id=1), started_at DATETIME NOT NULL)`.
- Create: `backend/src/backend/domain/ports/level_change_lock.py`
- Create: `backend/src/backend/infrastructure/persistence/sqla_level_change_lock.py` (+ model in the models module where others live)
- Modify: `backend/src/backend/domain/exceptions.py` — `LevelChangeInProgressError(DomainError)`.
- Modify: `backend/src/backend/infrastructure/persistence/database.py` — `release_level_change_lock(session_factory)` next to `release_source_operations`; `infrastructure/api/app.py` lifespan calls it (API only; the worker never).
- Test: `backend/tests/integration/test_level_change_lock.py`

**Interfaces:**
- Produces: `LevelChangeLock(ABC)`: `take() -> None` (raises `LevelChangeInProgressError` if held), `held() -> bool`, `release() -> None` (no-op if absent). `SqlaLevelChangeLock(session)`.

- [ ] Tests: `test_take_then_held`, `test_take_twice_raises`, `test_release_absent_is_noop`, `test_startup_release_clears_row`.
- [ ] Implement, `make test` on the file, commit `feat: level change lock row`.

### Task 2: Write gate in the unit of work

**Files:**
- Create: `backend/src/backend/infrastructure/persistence/write_gate.py`
- Modify: `backend/src/backend/infrastructure/persistence/sqla_unit_of_work.py` — ctor param `gate: WriteGate`; after `BEGIN IMMEDIATE` call `gate.admit(session)`; on `False` rollback, sleep `GATE_RETRY_SECONDS = 0.5`, begin again.
- Modify: `backend/src/backend/infrastructure/container.py` — `Container(..., write_gate: WriteGate)`; API builds with `RefuseDuringLevelChange()`, worker and TTS subprocess with `WaitOutLevelChange()`; `level_change_unit_of_work(session)` builds a UoW with `OwnLevelChange()` (same `before_commit` projector as `_unit_of_work`).
- Modify: `backend/src/backend/infrastructure/api/app.py` — exception handler `LevelChangeInProgressError → 423 {"detail": "level change in progress"}`.
- Test: `backend/tests/integration/test_write_gate.py`, `backend/tests/unit/architecture/test_writes_through_unit_of_work.py`

**Interfaces:**
- Produces: `WriteGate(ABC).admit(session: Session) -> bool` (True: go on; False: wait and retry; raise: refuse). `RefuseDuringLevelChange`, `WaitOutLevelChange` (also `waited_seconds() -> float`, total since creation, thread-safe), `OwnLevelChange` (always True).

- [ ] Tests: `test_refuse_gate_raises_while_locked_and_rolls_back`, `test_wait_gate_writes_after_release` (release from another thread after 1 s; write lands, `waited_seconds() >= 1`), `test_own_gate_writes_while_locked`, `test_any_gate_writes_when_unlocked`.
- [ ] Architecture test: AST scan of `backend/src` for `.commit(` calls; allowed only in `ALLOWED = {sqla_unit_of_work.py, sqla_parse_cache.py, database.py (startup helpers)}` plus each other place found, listed with a one-line reason; a new file with `.commit(` fails the test.
- [ ] Implement, run `make test`, commit `feat: refuse or wait writes during a level change`.

### Task 3: Worker timeout ignores the wait

**Files:**
- Modify: `backend/src/backend/infrastructure/queue/job_worker.py` — replace `asyncio.wait_for(..., JOB_TIMEOUT)` by `_run_within_timeout(work)` whose deadline moves forward by the growth of `gate.waited_seconds()` during the run.
- Test: `backend/tests/unit/infrastructure/test_job_worker_timeout.py` (or the existing worker test module)

- [ ] Tests: `test_wait_at_gate_does_not_count` (fake gate reporting 900 s of waiting, work finishing at 700 s of fake time → not timed out), `test_plain_overrun_still_times_out`.
- [ ] Implement, commit `fix: worker timeout excludes waiting out a level change`.

### Task 4: Source rebuilder parts

**Files:**
- Modify: `backend/src/backend/application/utils/source_rebuilder.py`

**Interfaces:**
- Produces: `analyse(source_id: int, values: AnalysisValues | None = None) -> AnalysedSource` — `AnalysisValues(user_level: str, frequent_word_zipf: float)` frozen dataclass; `None` = read settings as now. `apply_inside(analysed, mode) -> AppliedSource` — the body of `apply` without its own transaction and without removing files; `AppliedSource(plan: RebuildPlan, dropped_files: list[...])`. `apply` = `write()` + `apply_inside` + remove files (behaviour unchanged).
- Threshold → zipf for the new value: use `FrequentWordThresholdResolver` the way `resolve()` does, for a given key and level (add `resolve_for(key: str, level: str)` if `resolve()` reads settings).

- [ ] Tests (`backend/tests/integration/test_rebuild_source.py` style): `test_analyse_uses_given_level_not_saved_one`, `test_apply_inside_needs_open_write` (raises / writes nothing outside a write).
- [ ] Implement, commit `refactor: source rebuilder analyses with given values and applies inside a write`.

### Task 5: Level change use case

**Files:**
- Create: `backend/src/backend/domain/services/level_change_progress.py` — `percent(stage: LevelChangeStage, done: int, total: int) -> int`; `LevelChangeStage` enum ANALYSE / APPLY / FINISH; shares `ANALYSE_SHARE`, `APPLY_SHARE`, `FINISH_SHARE` (start 70/20/10, set from Task 8 numbers). 100 only via `LevelChangeProgress.succeed()`.
- Create: `backend/src/backend/application/utils/level_change_progress.py` — `LevelChangeProgress` (thread-safe): `begin()`, `step(stage, done, total)`, `cancel() -> bool` (False when not running or in FINISH), `cancel_requested() -> bool`, `succeed()`, `fail(message)`, `cancelled()`, `status() -> LevelChangeStatusDTO`.
- Create: `backend/src/backend/application/dto/level_change_dtos.py` — `LevelChangeStatusDTO(running: bool, percent: int, cancellable: bool, outcome: Literal["succeeded","cancelled","failed"] | None, error: str | None)`.
- Create: `backend/src/backend/application/use_cases/change_level.py`
- Modify: `backend/src/backend/domain/exceptions.py` — `LevelChangeCancelledError`.

**Interfaces:**
- Produces: `ChangeLevelUseCase.start(request: UpdateSettingsRequest) -> None` — in one normal write: refuse with `SourceOperationBusyError` if any `source_operations` row; `lock.take()`. `ChangeLevelUseCase.run(request, progress) -> None` — stage 1 over the targets of `SourceScope.all()` offering UPDATE (same filter as `ScopeOperationUseCase._targets`), `cancel_requested()` checked before each source; stage 2 in `level_change_unit_of_work.write()`: write settings (shared helper with `ManageSettingsUseCase._write_settings`), `apply_inside` each with cancel check, `progress.step(FINISH…)`, `lock.release()`; after commit remove all dropped files. Any exception or cancel: lock released in an own-gate write, progress `fail`/`cancelled`.
- Consumes: Task 1 lock, Task 2 own UoW, Task 4 rebuilder.

- [ ] Tests (`backend/tests/integration/test_change_level.py`): `test_success_applies_level_sources_and_states` (projection equals full calc: reuse `card-states-check` comparer), `test_failure_on_second_source_changes_nothing` (settings, phrases, `card_states` byte-equal before/after), `test_cancel_in_analyse_writes_nothing`, `test_cancel_in_apply_rolls_back`, `test_cannot_cancel_in_finish`, `test_start_refused_when_source_busy`, `test_start_refused_when_locked`, `test_topic_source_sections_only`, `test_threshold_only_change_goes_the_same_way`, `test_percent_monotonic`.
- [ ] Implement, commit `feat: change level in one transaction`.

### Task 6: Settings save and API

**Files:**
- Modify: `backend/src/backend/application/use_cases/manage_settings.py` — if a trigger key would change (compare request to stored), call `LevelChangeLauncher.start(request)` and write nothing; else as now.
- Replace: `domain/ports/sources_rebuild_launcher.py` → `domain/ports/level_change_launcher.py` (`start(request) -> None`); `infrastructure/api/background_rebuild_launcher.py` → `infrastructure/api/background_level_change.py` (calls `ChangeLevelUseCase.start` synchronously so 409 reaches the request, then runs `run` on a daemon thread with its own session). Delete `RebuildPasses` and its tests.
- Create: `backend/src/backend/infrastructure/api/routes/level_change.py` — `GET /api/level-change` → `LevelChangeStatusDTO`; `POST /api/level-change/cancel` → 202, 409 if not cancellable. Register router.
- Modify tests: `test_settings_rebuild_trigger.py`, `test_settings_rebuild_all.py`, `test_api_settings.py`, `conftest.py`, `test_card_state_projection_differential.py` to the new launcher.
- Test: `backend/tests/integration/test_api_level_change.py`

- [ ] Tests: `test_patch_returns_at_once_and_status_runs`, `test_second_patch_during_change_is_409`, `test_write_endpoint_during_change_is_423` (e.g. a review decision), `test_reads_work_during_change`, `test_cancel_endpoint`, `test_non_trigger_patch_saves_directly`.
- [ ] `make test lint typecheck` green, commit `feat: settings save starts the atomic level change`.

### Task 7: Frontend loader

**Files:**
- Modify: `frontends/web/src/api/types.ts`, `client.ts` (`getLevelChange`, `cancelLevelChange`), `errors.ts` (`LEVEL_CHANGE_STATUS = 423`; `send` emits a `level-change` signal on 423).
- Create: `frontends/web/src/shell/levelChange.ts` (signal + `useLevelChange` hook: fetch on mount, on window focus, on the signal, after settings save; poll every 1000 ms while `running`), `frontends/web/src/shell/LevelChangeOverlay.tsx` + `.module.css`: fixed full-window backdrop catching all pointer and key events; centered big percent; `Cancel` button disabled when `!cancellable`.
- Modify: `AppShell.tsx` renders the overlay; `useSettings.ts` signals after save. On `running → !running`: `succeeded` → `location.reload()`; `failed` → shell `Banner` with `error`, dismissible; `cancelled` → settings reloaded.
- Test: `frontends/web/src/shell/LevelChangeOverlay.test.tsx` — renders percent, Cancel disabled when not cancellable, appears on 423 signal.

- [ ] Screenshots (headless, wide + narrow, light + dark) of the overlay at 37 % with a real settings screen beneath; self-critique against `quiet secondary UI` and spacing memories before keeping.
- [ ] `npm run lint`, `npm run build`, `npx vitest run` green; commit `feat: level change loader with percent and cancel`.

### Task 8: Measure and verify

- [ ] `make bench-db EPUB=… CHAPTERS=0 OUT=$BENCH/worm-all.db` (outside repo), run the change B1→B2 on a copy via a small script `scripts/bench/bench_level_change.py` (+ `make bench-level-change DB=… OUT=…`): stage times, peak RSS, percent vs time samples. Set shares in Task 5 so percent is ~linear in time. Write numbers to `internal/specs/atomic-level-change-bench.md`.
- [ ] If peak RSS of stage 1 > 2 GB: keep analyses in a temp file per source instead of memory (spec allows), re-measure.
- [ ] `kill -9` of the API mid stage 1 and mid stage 2 on a worktree copy: after `make up-worktree` the old level, no lock, `make card-states-check` 0 differences.
- [ ] Real app in worktree: change level on dev data copy, overlay shows, Cancel works, a second tab shows overlay.
- [ ] Whole-branch review (fresh reviewer), fix findings, full `make test lint typecheck`, frontend checks.
