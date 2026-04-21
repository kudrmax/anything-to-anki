# Reprocess Source Design

## Problem

After changing settings (e.g. target CEFR level B1 -> B2) or updating pipeline algorithms (improved segmentation, better ranking), there is no way to re-run the pipeline on already-processed sources. Users must delete and re-add the source manually, losing all context.

## Approach: Delete + Re-create

Full reset: delete all candidates for the source (CASCADE removes meanings, media, pronunciation, cefr_breakdowns, anki_synced_cards), reset source to initial state, re-run existing `ProcessSourceUseCase`. No modifications to the pipeline itself.

### Why this works without data loss

- **KNOWN words** are already persisted in `known_words` table (lemma + pos pairs). Pipeline filters them out automatically on re-run.
- **LEARN words** — user is prompted to export to Anki before reprocessing. After export, candidates are marked KNOWN -> added to `known_words`.
- **SKIP words** — loss is acceptable.
- **Enrichments** (meanings, media, pronunciation) are regenerated via the same flow as initial processing.

## Backend

### Source.reset_to_initial_state()

Method on the `Source` entity that returns a **new** `Source` instance, copying only input fields (what the user originally provided at creation), everything else gets dataclass defaults.

Two frozensets defined alongside the method:

```python
_SOURCE_INPUT_FIELDS = frozenset({
    "id", "raw_text", "title", "input_method", "content_type",
    "source_url", "video_path", "audio_track_index", "created_at",
})

_SOURCE_DERIVED_FIELDS = frozenset({
    "status", "cleaned_text", "error_message", "processing_stage",
})
```

Test enforces completeness:
- `_SOURCE_INPUT_FIELDS | _SOURCE_DERIVED_FIELDS == all fields of Source`
- `_SOURCE_INPUT_FIELDS & _SOURCE_DERIVED_FIELDS == empty set`

Adding a field to `Source` without classifying it breaks the test.

### ReprocessSourceUseCase

Single method `execute(source_id)`:

1. Load source, verify status in {DONE, PARTIALLY_REVIEWED, REVIEWED, ERROR}
2. Check no active enrichment jobs via three ports:
   - `candidate_meaning_repo.has_active_by_source(source_id)`
   - `candidate_media_repo.has_active_by_source(source_id)`
   - `candidate_pronunciation_repo.has_active_by_source(source_id)`
   Each port checks for RUNNING or QUEUED statuses in its own table. If any returns true — raise domain error (mapped to 409 at API level).
3. `candidate_repo.delete_by_source(source_id)` — new method on `CandidateRepository` port. CASCADE deletes all related records
4. `source.reset_to_initial_state()` -> persist updated source to DB
5. `ProcessSourceUseCase.start(source_id)` — validates and marks PROCESSING

The use case does NOT enqueue the worker job — that is infrastructure. The route handler calls `use_case.execute()`, then enqueues the arq job, same pattern as the existing process endpoint.

### API Endpoints

**`GET /api/sources/{source_id}/reprocess-stats`**

Returns candidate counts and active job status for the confirmation modal:

```json
{
  "learn_count": 5,
  "known_count": 0,
  "skip_count": 12,
  "pending_count": 8,
  "has_active_jobs": true
}
```

`has_active_jobs`: true if any of the three enrichment repositories (`has_active_by_source`) returns true. Computed by a use case (e.g. `GetReprocessStatsUseCase`), not directly in the route.

**`POST /api/sources/{source_id}/reprocess`**

- Validates no active jobs (409 Conflict if found — backend does not trust frontend)
- Calls `ReprocessSourceUseCase.execute(source_id)`
- Returns 202 Accepted

### Allowed source statuses

- DONE, PARTIALLY_REVIEWED, REVIEWED — full modal flow
- ERROR — reprocess immediately, no modal (nothing to lose)
- NEW, PROCESSING — not allowed

## Frontend

### Entry point

Reprocess button in the sources list (actions/context menu). Visible only for sources with status DONE, PARTIALLY_REVIEWED, REVIEWED, or ERROR.

### Flow by status

**ERROR:** No modal. Direct `POST /reprocess`. Nothing to lose.

**DONE / PARTIALLY_REVIEWED / REVIEWED:**

1. Fetch `GET /reprocess-stats`
2. Show custom modal (not browser confirm)

### Modal content

Always show counts:

```
Will be lost:
X learn words
Y known words
Z skip words
```

**If `learn_count > 0` or `known_count > 0`** — show warning block:
> "To preserve Learn words, export them to Anki first."

**If both are 0** — no warning block, just counts.

**If `has_active_jobs: true`** — "Reprocess source" button is disabled, message:
> "Source has active jobs (meaning/media generation). Cancel them on the source page before reprocessing."

### Buttons

1. **"Open export page"** — primary (bright), default. Opens export page for this source.
2. **"Reprocess source"** — destructive (red). Calls `POST /reprocess`, closes modal.

## Testing

### Unit tests

- **`test_all_source_fields_classified`** — `_SOURCE_INPUT_FIELDS | _SOURCE_DERIVED_FIELDS == all fields`, no intersection
- **`test_reset_to_initial_state`** — derived fields get defaults, input fields preserved
- **`ReprocessSourceUseCase`**:
  - Reprocess DONE source — candidates deleted, source reset, ProcessSourceUseCase called
  - Reprocess ERROR source — same flow, works without candidates
  - Reprocess PROCESSING/NEW source — raises error
  - Reprocess with active jobs (RUNNING/QUEUED enrichments) — raises error
- **`reprocess-stats` endpoint** — correct counts by candidate status, has_active_jobs flag
- **`reprocess` endpoint** — 202 for valid, 409 for active jobs, 400/404 for invalid status/missing source

### Integration tests

- **Full reprocess cycle**: create source -> process -> mark some candidates LEARN/KNOWN/SKIP -> reprocess -> verify:
  - Old candidates and their enrichments are gone
  - New candidates created with PENDING status
  - KNOWN words from `known_words` table are filtered out in new candidates
  - Source status transitions: DONE -> NEW -> PROCESSING -> DONE
- **Reprocess with active jobs blocked**: create source -> process -> set enrichment to RUNNING -> attempt reprocess -> 409 -> cancel enrichment -> reprocess succeeds
- **ERROR source reprocess**: create source -> force ERROR status -> reprocess -> verify pipeline runs successfully

## Scope exclusions

- No batch reprocess (all sources at once) — single source only
- No enrichment transfer from old to new candidates (YAGNI)
- No soft-delete / history of old candidates
