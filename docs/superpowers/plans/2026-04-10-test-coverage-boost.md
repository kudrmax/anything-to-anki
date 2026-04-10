# Test coverage boost — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Поднять покрытие критичных модулей backend (AI, очереди, AnkiConnect, ключевые use cases) с 80.6% до ~88-90%, фокусируясь на реальной логике через TDD.

**Architecture:** Все новые тесты — unit-уровень с моками портов / `httpx` / `claude_agent_sdk.query`. Никаких реальных сетевых вызовов. Тесты живут в существующих директориях `backend/tests/unit/{infrastructure,application}/`.

**Tech Stack:** pytest, pytest-asyncio, unittest.mock (MagicMock, AsyncMock, patch).

---

## Workflow per task

Для каждого модуля:
1. Прочитать прод-файл целиком, перечислить непокрытые ветки.
2. Для каждой ветки сформулировать **наблюдаемый эффект** (что должен показывать тест).
3. Написать тест → запустить → убедиться, что упал по правильной причине (или прошёл, если код уже соответствует — тогда зафиксировать как regression guard).
4. Если найден баг — `# TODO: bug — see tasks/<file>.md`, тест пометить `pytest.xfail`, файл задачи в `tasks/`. Маленькие баги — fix-коммит сразу.
5. Запустить cov на конкретный модуль — убедиться что missing уменьшился.
6. Коммит: `test: cover <module>` (или `feat:` если был fix).

После каждой таски — финальный прогон `pytest -q` всем набором, чтобы убедиться, что ничего не сломали.

---

## Task 1: Cover claude_ai_service.py (0% → ≥90%)

**Files:**
- Create: `backend/tests/unit/infrastructure/test_claude_ai_service.py`
- Reference: `backend/src/backend/infrastructure/adapters/claude_ai_service.py`

**Scenarios** (each = one test):

1. `test_generate_meaning_happy_path_dict_structured` — `query` yields `ResultMessage` with `structured_output={meaning, translation, synonyms, ipa}` as dict. Returns `GenerationResult` with correct fields and `tokens_used = input + output`.
2. `test_generate_meaning_happy_path_json_string_structured` — same but `structured_output` is JSON string. Same result.
3. `test_generate_meaning_no_structured_output_raises` — `query` yields `ResultMessage` with `structured_output=None` → `AIServiceError("No structured output...")`.
4. `test_generate_meaning_cli_not_found_raises_with_install_hint` — `query` raises `CLINotFoundError` → `AIServiceError("Claude Code CLI not found. Install...")`.
5. `test_generate_meaning_cli_connection_error_raises_with_login_hint` — `query` raises `CLIConnectionError` → `AIServiceError("Cannot connect to Claude. Run 'claude' to log in.")`.
6. `test_generate_meaning_process_error_raises_with_exit_code` — `query` raises `ProcessError(exit_code=2)` → `AIServiceError` mentioning exit code.
7. `test_generate_meaning_async_exception_with_auth_keyword_raises_auth_hint` — `query` raises `RuntimeError("Authentication failed")` → `AIServiceError("Not authenticated...")`.
8. `test_generate_meaning_async_exception_with_stderr_uses_stderr` — `query` raises generic `RuntimeError` and `stderr` callback was called → error detail uses stderr.
9. `test_generate_meaning_async_generic_exception_raises_ai_error` — generic `RuntimeError("oops")` → `AIServiceError("oops")`.
10. `test_generate_meanings_batch_happy_path` — batch returns list of `BatchMeaningResult` with all word_indexes and content.
11. `test_generate_meanings_batch_no_structured_output_raises` — error path.
12. `test_generate_meanings_batch_cli_not_found_raises` — error path.
13. `test_generate_meanings_batch_auth_error_raises_auth_hint`.

**Mocking helper** (define inside test file):

```python
from unittest.mock import patch, MagicMock
import pytest
from backend.domain.exceptions import AIServiceError

class _ResultMessage:
    """Stand-in for claude_agent_sdk.ResultMessage so isinstance check passes."""
    def __init__(self, structured_output=None, usage=None):
        self.structured_output = structured_output
        self.usage = usage

def _async_iter(items):
    async def _gen():
        for item in items:
            yield item
    return _gen()

def _patch_query(messages=None, exc=None):
    """Patch claude_agent_sdk.query as imported in claude_ai_service module."""
    def fake_query(prompt, options):
        if exc is not None:
            raise exc
        return _async_iter(messages or [])
    return patch(
        "backend.infrastructure.adapters.claude_ai_service.query",
        side_effect=fake_query,
    )
```

**Note on isinstance:** the production code does `isinstance(message, ResultMessage)` where `ResultMessage` is imported from `claude_agent_sdk`. To make our fake messages match, also patch `ResultMessage` in the module:

```python
@pytest.fixture
def patched_module():
    with patch("backend.infrastructure.adapters.claude_ai_service.ResultMessage", _ResultMessage):
        yield
```

Use the fixture in every test that needs `query` to yield messages.

**Steps:**
- [ ] Write helper + first test (`happy_path_dict_structured`). Run, expect PASS (cover ~30 lines). Commit.
- [ ] Add tests 2-9 (single generation paths). Run after each (or batch of 2-3). Commit.
- [ ] Add tests 10-13 (batch generation paths). Commit.
- [ ] Run cov: `.venv/bin/python -m pytest backend/tests/unit/infrastructure/test_claude_ai_service.py --cov=backend.infrastructure.adapters.claude_ai_service --cov-report=term-missing -q` — verify ≥90%.

---

## Task 2: Cover http_ai_service.py (24% → ≥95%)

**Files:**
- Create: `backend/tests/unit/infrastructure/test_http_ai_service.py`
- Reference: `backend/src/backend/infrastructure/adapters/http_ai_service.py`

**Scenarios:**

1. `test_generate_meaning_happy_path` — `httpx.post` returns 200 with full JSON. Verify endpoint URL, payload (system_prompt, user_prompt, model), parsed `GenerationResult`.
2. `test_generate_meaning_strips_trailing_slash_from_url` — pass `url="http://x/"`, verify request endpoint is `http://x/generate-meaning`.
3. `test_generate_meaning_missing_ipa_defaults_to_none` — response without `ipa` field → `result.ipa is None`.
4. `test_generate_meaning_missing_tokens_used_defaults_to_zero`.
5. `test_generate_meaning_connect_error_raises_proxy_hint` — `httpx.ConnectError` → `AIServiceError("Cannot connect to AI proxy...")`.
6. `test_generate_meaning_http_status_error_includes_response_body` — `HTTPStatusError(response with text="bad")` → `AIServiceError("AI proxy error: bad")`.
7. `test_generate_meaning_unexpected_exception_wrapped` — generic `ValueError("x")` raised → `AIServiceError("x")`.
8. `test_generate_meanings_batch_happy_path` — list of 3 results parsed correctly.
9. `test_generate_meanings_batch_uses_540s_timeout` — verify call kwarg.
10. `test_generate_meanings_batch_connect_error_raises`.
11. `test_generate_meanings_batch_http_status_error_raises`.
12. `test_generate_meanings_batch_unexpected_exception_wrapped`.

**Mocking pattern:**

```python
from unittest.mock import patch, MagicMock
import httpx
import pytest
from backend.infrastructure.adapters.http_ai_service import HttpAIService
from backend.domain.exceptions import AIServiceError

def _mock_response(json_data, status_code=200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp

def _http_error(status_code, body):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = body
    return httpx.HTTPStatusError("err", request=MagicMock(), response=resp)
```

**Steps:**
- [ ] Write helpers + tests 1-7. Run. Commit.
- [ ] Write tests 8-12. Run. Commit.
- [ ] Verify coverage on module ≥95%.

---

## Task 3: Cover enqueue_meaning_generation.py (0% → 100%)

**Files:**
- Create: `backend/tests/unit/application/test_enqueue_meaning_generation.py`

**Scenarios:**

1. `test_relevance_sort_returns_batches_of_15` — `meaning_repo.get_candidate_ids_without_meaning(only_active=True, sort_order=RELEVANCE)` returns list of 32 ids → result is `[[1..15], [16..30], [31..32]]`. Verify `mark_queued_bulk` called with all 32.
2. `test_relevance_sort_empty_returns_empty` — repo returns `[]` → result `[]`, no `mark_queued_bulk`, log line still emitted.
3. `test_relevance_sort_default_when_none` — `sort_order=None` → still uses RELEVANCE branch (the `else` branch).
4. `test_chronological_re_sorts_by_text_position` — repo returns `[3, 1, 2]`. Source text is `"foo bar baz qux"`. Candidate fragments: id=1→"baz", id=2→"qux", id=3→"foo". After sorting by `text.find(fragment)`: order should be `[3, 1, 2]` (foo@0 < baz@8 < qux@12). Returns `[[3, 1, 2]]`.
5. `test_chronological_empty_returns_empty_without_lookup` — repo returns `[]`. `source_repo.get_by_id` and `candidate_repo.get_by_ids` not called.
6. `test_chronological_source_not_found_returns_empty` — repo returns ids, but `source_repo.get_by_id` returns `None` → returns `[]`, `mark_queued_bulk` NOT called.
7. `test_chronological_uses_raw_text_when_cleaned_text_is_none` — source has `cleaned_text=None`, `raw_text="foo bar baz"`. Verify sorting uses raw_text.

**Mocking pattern:**

```python
from unittest.mock import MagicMock
from backend.application.use_cases.enqueue_meaning_generation import EnqueueMeaningGenerationUseCase
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.candidate_status import CandidateStatus

def _make_source(text="foo bar baz", cleaned=None):
    return Source(
        id=1, raw_text=text, cleaned_text=cleaned,
        status=SourceStatus.READY,
    )

def _make_candidate(id_, fragment):
    return StoredCandidate(
        id=id_, source_id=1, lemma="x", pos="NOUN",
        cefr_level=None, zipf_frequency=5.0, is_sweet_spot=False,
        context_fragment=fragment, fragment_purity="clean",
        occurrences=1, surface_form=None, is_phrasal_verb=False,
        status=CandidateStatus.PENDING,
    )
```

**Steps:**
- [ ] Write tests 1-3 (RELEVANCE branch). Run. Commit.
- [ ] Write tests 4-7 (CHRONOLOGICAL branch). Run. Commit.
- [ ] Verify cov on module = 100%.

---

## Task 4: Cover enqueue_media_generation.py (0% → 100%)

**Files:**
- Create: `backend/tests/unit/application/test_enqueue_media_generation.py`

Mirror Task 3, but for media:

1. `test_relevance_returns_eligible_ids_and_marks_queued` — repo returns `[10, 20, 30]` → returns `[10, 20, 30]`, `mark_queued_bulk([10, 20, 30])`.
2. `test_relevance_empty_returns_empty`.
3. `test_relevance_default_when_none` — sort_order=None.
4. `test_chronological_re_sorts_by_text_position`.
5. `test_chronological_empty_skips_source_lookup`.
6. `test_chronological_source_not_found_returns_empty`.
7. `test_chronological_uses_raw_text_when_cleaned_text_is_none`.

**Steps:** mirror Task 3.

---

## Task 5: Cover anki_connect_connector.py (49% → ≥90%)

**Files:**
- Modify: `backend/tests/unit/infrastructure/test_anki_connect_connector.py` (add classes)
- Reference: `backend/src/backend/infrastructure/adapters/anki_connect_connector.py`

**Existing tests:** only `ensure_note_type` (4 tests). Add:

**`TestInvoke`:**
1. `test_invoke_posts_correct_payload_and_returns_result` — patch `httpx.post` to return `{"result": 42}` → `_invoke("version")` returns `42`. Verify URL, json keys (`action`, `version`, `params`).
2. `test_invoke_raises_runtime_error_on_anki_error_field` — response `{"error": "deck missing"}` → `RuntimeError("AnkiConnect error: deck missing")`.
3. `test_invoke_raises_on_http_error` — `raise_for_status` raises `HTTPStatusError` → propagates.

**`TestGetVersion`:**
4. `test_get_version_returns_int` — _invoke returns int → returns same int.

**`TestIsAvailable`:**
5. `test_is_available_returns_true_when_version_succeeds` — patch `_invoke` to return 6 → `True`.
6. `test_is_available_returns_false_on_connect_error` — `_invoke` raises `httpx.ConnectError` → `False`.
7. `test_is_available_returns_false_on_runtime_error` — `_invoke` raises `RuntimeError` → `False` (the bare-Exception branch).

**`TestEnsureDeck`:**
8. `test_ensure_deck_calls_create_deck_action`.

**`TestFindNotesByTarget`:**
9. `test_find_notes_returns_list_when_present` — _invoke returns `[1, 2, 3]`.
10. `test_find_notes_returns_empty_list_when_none` — _invoke returns `None` → `[]`.
11. `test_find_notes_query_uses_target_and_model_name` — verify the query string.

**`TestAddNotes`:**
12. `test_add_notes_wraps_each_note_with_options_and_tags` — input: list of 2 dicts of fields, verify _invoke called with `notes=[...]` containing `deckName`, `modelName`, `fields`, `options.allowDuplicate=False`, `tags=["anything-to-anki"]`.
13. `test_add_notes_returns_anki_ids` — _invoke returns `[101, None, 102]` → returned as-is.
14. `test_add_notes_returns_empty_list_when_invoke_returns_none`.

**`TestGetModelFieldNames`:**
15. `test_get_model_field_names_returns_fields_when_model_present`.
16. `test_get_model_field_names_returns_none_when_model_missing`.
17. `test_get_model_field_names_returns_none_on_invoke_error` — _invoke raises → returns None.

**`TestStoreMediaFile`:**
18. `test_store_media_file_base64_encodes_file_content` — write a temp file, call store_media_file, verify _invoke called with correct base64 of the file content.

**Mocking pattern (for _invoke at httpx level):**

```python
from unittest.mock import MagicMock, patch
def _httpx_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp
```

For `_invoke` tests use `patch("backend.infrastructure.adapters.anki_connect_connector.httpx.post", return_value=_httpx_response(...))`.
For other tests use `patch.object(connector, "_invoke", ...)`.

**Steps:**
- [ ] Add `TestInvoke` (3 tests). Run. Commit.
- [ ] Add `TestGetVersion`, `TestIsAvailable` (4 tests). Commit.
- [ ] Add `TestEnsureDeck`, `TestFindNotesByTarget` (4 tests). Commit.
- [ ] Add `TestAddNotes` (3 tests). Commit.
- [ ] Add `TestGetModelFieldNames`, `TestStoreMediaFile` (4 tests). Commit.
- [ ] Verify cov ≥90%.

---

## Task 6: Cover add_manual_candidate.py (22% → ≥90%)

**Files:**
- Create: `backend/tests/unit/application/test_add_manual_candidate.py`

**Scenarios:**

1. `test_raises_source_not_found_when_source_missing` — `source_repo.get_by_id` returns None → `SourceNotFoundError`.
2. `test_creates_candidate_for_simple_word_match_in_context` — context "I want to procrastinate today", surface_form="procrastinate". Mock `text_analyzer.analyze` to return tokens including one with text="procrastinate" lemma="procrastinate" pos="VERB" tag="VB". Mock `phrasal_verb_detector.detect` to return `[]`. Mock cefr → C1, frequency → 4.5. Verify resulting candidate.lemma="procrastinate", pos="VERB", cefr_level="C1", is_phrasal_verb=False, occurrences computed from source text count.
3. `test_creates_candidate_for_phrasal_verb_match` — surface_form="give in", phrasal_verb_detector returns match with `lemma="give in"`, `verb_index=0`. Verify candidate has `is_phrasal_verb=True`, `lemma="give in"`, `pos="VERB"`.
4. `test_phrasal_verb_match_uses_verb_token_tag_when_token_present` — verb_index points to existing token with tag="VBP" → tag passed to cefr classifier is "VBP".
5. `test_phrasal_verb_match_falls_back_to_VB_tag_when_token_missing` — verb_index points to token not in token_map (impossible normally; defensive) → tag="VB".
6. `test_falls_back_to_surface_form_analysis_when_word_not_in_context` — context "lorem ipsum", surface_form="dolor". First `analyze(context)` returns tokens for "lorem ipsum" only. Second `analyze(surface_form)` returns token for "dolor". Verify lemma comes from second analysis.
7. `test_uses_X_pos_when_no_token_found_anywhere` — neither analysis yields a matching token → pos="X", tag="NN", lemma=surface_lower.
8. `test_occurrences_at_least_1_when_word_not_in_source_text` — source text has no occurrences → occurrences=1.
9. `test_occurrences_counts_case_insensitive_in_source_text` — source has 3 occurrences of "Word" → occurrences=3.
10. `test_uses_raw_text_when_cleaned_text_is_none`.
11. `test_cefr_unknown_results_in_none_cefr_level` — classifier returns UNKNOWN → DTO `cefr_level=None`.

**Mocking pattern:**

```python
from unittest.mock import MagicMock
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.frequency_band import FrequencyData
from backend.domain.entities.token_data import TokenData

def _token(index, text, lemma, pos="NOUN", tag="NN"):
    return TokenData(
        index=index, text=text, lemma=lemma, pos=pos, tag=tag,
        is_alpha=True, is_punct=False, is_stop=False, dep="", head=0,
    )
```

(Adjust dataclass fields to actual TokenData definition — read it first.)

**Steps:**
- [ ] Read `backend/src/backend/domain/entities/token_data.py` and `frequency_band.py` to confirm constructors.
- [ ] Write tests 1-5 (validation + phrasal verb branch). Commit.
- [ ] Write tests 6-11 (regular word branch + edges). Commit.
- [ ] Verify cov on module ≥90%.

---

## Task 7: Cover missing branches in run_generation_job.py (93% → 100%)

**Files:**
- Modify: `backend/tests/unit/application/test_run_generation_job.py`

**Missed lines: 54-57 (all candidates filtered out → early return) and 82 (current.status != RUNNING → cancelled).**

**Scenarios:**

1. `test_returns_early_when_all_candidates_filtered_out_by_status` — all candidates are KNOWN status (or already have meaning) → AI service NOT called. Use case returns without raising.
2. `test_skips_candidate_when_meaning_status_is_not_running_anymore` — meaning_repo.get_by_candidate_id returns a meaning with status=DONE (or QUEUED, anything but RUNNING) → that candidate is skipped (cancelled++), upsert NOT called for it.

**Steps:**
- [ ] Add 2 tests to existing file. Run. Commit. Verify cov = 100%.

---

## Task 8: Cover workers.py startup/shutdown (95% → 100%)

**Files:**
- Modify: `backend/tests/unit/infrastructure/test_workers.py`

**Missed lines: 104-105, 109 (startup, shutdown).**

**Scenarios:**

1. `test_worker_startup_creates_container_in_ctx` — call `await startup({})`, verify ctx contains `"container"` key with a `Container` instance. Patch `Container` to avoid heavy DI initialization.
2. `test_worker_shutdown_runs_without_error` — call `await shutdown({})`, no exception.

**Steps:**
- [ ] Add 2 tests. Run. Commit. Verify cov = 100%.

---

## Final task: Coverage report and cleanup

- [ ] Run full suite: `.venv/bin/python -m pytest --cov=backend/src/backend --cov-report=term --cov-report=json:coverage-final.json -q`
- [ ] Compare baseline.json vs final.json — produce per-module delta.
- [ ] Write report: `docs/superpowers/specs/2026-04-10-test-coverage-boost-report.md` with quant + qual sections.
- [ ] Commit report.
- [ ] If any tasks/<file>.md were created — list them in the report.

---

## Self-review

- **Spec coverage:** All 8 priority targets in spec are addressed by tasks 1-8. Out-of-scope items (routes, container, alembic, frontend) explicitly excluded in spec — no tasks needed.
- **Placeholder scan:** No "TBD" / "implement later". Test scenarios are concrete with names and expected behavior.
- **Type consistency:** `GenerationResult`, `BatchMeaningResult`, `Source`, `StoredCandidate`, `CandidateSortOrder` referenced consistently with verified field names.
- **Bug handling:** TDD will reveal discrepancies; pre-decided policy in design (small fix inline, big xfail+task file).
