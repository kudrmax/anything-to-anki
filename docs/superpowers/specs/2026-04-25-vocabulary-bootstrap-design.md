# Vocabulary Bootstrap — Batch Known Words Calibration

## Goal

Let the user quickly mark many words as Known in bulk, so they don't appear in the normal pipeline. The user sees batches of 15 words at a time, clicks the ones they know, and moves on.

## Word Corpus

Words come from the dictionary cache (`dict.db`) — all unique `(lemma, pos)` pairs from the `cefr` table. The corpus is dynamic: whatever dictionaries the user has configured (Oxford 5000, Cambridge, EFLLex, Kelly, etc.) form the word pool. No hardcoded word lists.

## CEFR and Zipf — Same Functions as Pipeline

Classification MUST use the same domain ports used in the main pipeline:

- **CEFR**: `CEFRClassifier.classify(lemma, pos_tag) -> CEFRLevel`
- **Zipf**: `FrequencyProvider.get_zipf_value(lemma) -> float`

The Container injects the same implementations (VotingCEFRClassifier, WordfreqFrequencyProvider) as the pipeline. If classification logic changes, bootstrap automatically picks it up.

## Grid Parameters

The screen shows up to 15 words — one per cell in a 3x5 grid (CEFR rows x Zipf columns).

**CEFR rows**: X+1, X+2, X+3 where X is the user's CEFR setting. Example: user has B1 → grid shows B2, C1, C2. If user has B2 → grid is 2x5 (C1, C2). If user has C1 → grid is 1x5 (C2 only).

**Zipf columns**: [3.0, 3.5), [3.5, 4.0), [4.0, 4.5), [4.5, 5.0), [5.0, 5.5] — last band is inclusive on both ends

**Excluded**: CEFR UNKNOWN, Zipf outside [3.0, 5.5], phrasal verbs (pos = "phrasal verb"), already known words.

## CEFR Assignment Algorithm

A lemma can have multiple POS in the dict cache, each producing a different CEFR level via `VotingCEFRClassifier.classify(lemma, pos)`.

Algorithm:

1. For each lemma, collect all CEFR levels across its POS tags.
2. Intersect with the grid's CEFR levels.
3. If intersection is empty — skip the lemma (it won't appear in the pipeline anyway).
4. Take the **minimum** from the intersection — this is the cell's CEFR.

Example: grid = {B2, C1, C2}. Word `elaborate`: verb→B2, adjective→C1. Intersection = {B2, C1}. Minimum = B2. The word goes into the B2 row.

Example: grid = {B2, C1, C2}. Word `run`: verb→A1, noun→B1. Intersection = {} → not shown.

## Data Model

### Table `bootstrap_index_meta` (single row)

| Column     | Type        | Description                              |
|------------|-------------|------------------------------------------|
| id         | INTEGER PK  | Always 1                                 |
| status     | VARCHAR(20) | `none`, `building`, `ready`, `error`     |
| error      | TEXT NULL    | Error message when status=error          |
| built_at   | DATETIME NULL | When calibration data was last built    |
| word_count | INTEGER     | Number of words in calibration data      |

### Table `bootstrap_word_cell`

| Column     | Type         | Description                                    |
|------------|--------------|------------------------------------------------|
| lemma      | VARCHAR(100) | Lemma from dict cache                          |
| cefr_level | VARCHAR(2)   | CEFR level from VotingCEFRClassifier for one POS |
| zipf_value | FLOAT        | Zipf value from WordfreqFrequencyProvider      |
| PK         |              | `(lemma, cefr_level)`                          |

One lemma may have multiple rows — one per distinct CEFR level across its POS tags. Example:
```
(run, A1, 5.2)  -- classify(run, verb) → A1
(run, B1, 5.2)  -- classify(run, noun) → B1
```

The CEFR-to-grid-cell assignment happens at query time in the domain service, not at build time. This means the calibration data does NOT need rebuilding when the user changes their CEFR setting.

## Architecture (Clean)

### Domain

**Entity** `BootstrapWordEntry` (frozen dataclass):
- `lemma: str`, `cefr_level: CEFRLevel`, `zipf_value: float`

**Entity** `BootstrapIndexMeta` (frozen dataclass):
- `status: BootstrapIndexStatus`, `error: str | None`, `built_at: datetime | None`, `word_count: int`

**Value object** `BootstrapIndexStatus` (enum):
- `NONE`, `BUILDING`, `READY`, `ERROR`

**Port** `WordCorpusProvider` (ABC):
- `get_all_lemma_pos_pairs() -> list[tuple[str, str]]` — all (lemma, pos) from the word corpus

**Port** `BootstrapIndexRepository` (ABC):
- `get_meta() -> BootstrapIndexMeta`
- `set_meta(status, error?, built_at?, word_count?) -> None`
- `rebuild(entries: list[BootstrapWordEntry]) -> None` — truncate + bulk insert
- `get_all_entries() -> list[BootstrapWordEntry]`

**Domain service** `BootstrapWordSelector`:
- `select_words(entries, grid_levels, known_lemmas, excluded_lemmas) -> list[BootstrapWordEntry]`
- Algorithm:
  1. Filter out known_lemmas and excluded_lemmas
  2. For each lemma: collect all its cefr_levels, intersect with grid_levels, take minimum → cell_cefr
  3. Compute zipf_band from zipf_value
  4. Group by (cell_cefr, zipf_band)
  5. Pick one random word from each group
  6. Shuffle the result

### Application

**Use case** `BuildBootstrapIndexUseCase`:
- Dependencies: `WordCorpusProvider`, `CEFRClassifier`, `FrequencyProvider`, `BootstrapIndexRepository`
- Algorithm:
  1. Set meta status = BUILDING
  2. Get all (lemma, pos) pairs from WordCorpusProvider
  3. For each pair: `classify(lemma, pos)` → CEFRLevel
  4. For each unique lemma: `get_zipf_value(lemma)` → float
  5. Filter: CEFR != UNKNOWN, zipf in [3.0, 5.5], pos != "phrasal verb"
  6. `rebuild(entries)` — write to DB
  7. Set meta status = READY, word_count, built_at
  8. On error: set meta status = ERROR with error message
- Timeout: 300 seconds (measure real time during implementation, adjust)

**Use case** `GetBootstrapWordsUseCase`:
- Dependencies: `BootstrapIndexRepository`, `KnownWordRepository`, `SettingsRepository`, `BootstrapWordSelector`
- Algorithm:
  1. Read user's cefr_level from settings → compute grid_levels (X+1, X+2, X+3)
  2. Get all entries from BootstrapIndexRepository
  3. Get known lemmas from KnownWordRepository
  4. Call `BootstrapWordSelector.select_words(entries, grid_levels, known_lemmas, excluded_lemmas)`
  5. Return list of BootstrapWordDTO

**Existing use case** `ManageKnownWordsUseCase` — extend with bulk add:
- New method: `add_bulk(lemmas: list[str]) -> None` — for each lemma: `add(lemma, pos=None)`
- No new use case needed; reuse the existing one to avoid duplication

**DTOs**: `BootstrapStatusDTO`, `BootstrapWordDTO`, `SaveBootstrapWordsRequest`

### Infrastructure

**Adapter** `DictCacheWordCorpusProvider`:
- Implements `WordCorpusProvider`
- New method in `DictCacheReader`: `get_all_lemma_pos_pairs() -> list[tuple[str, str]]`
- Queries: `SELECT DISTINCT lemma, pos FROM cefr`

**Persistence** `SqlaBootstrapIndexRepository`:
- Implements `BootstrapIndexRepository`
- Two SQLAlchemy models: `BootstrapIndexMetaModel`, `BootstrapWordCellModel`

**Alembic migration** for both tables.

**Container**: wire all three use cases with their dependencies.

## API Endpoints

| Method | Path                    | Description                                      |
|--------|-------------------------|--------------------------------------------------|
| GET    | `/api/bootstrap/status` | Returns BootstrapStatusDTO                       |
| POST   | `/api/bootstrap/build`  | Start async build. Returns 202. 409 if building. |
| POST   | `/api/bootstrap/words`  | Body: `{"excluded": [...]}`. Returns up to 15 words. |
| POST   | `/api/bootstrap/known`  | Body: `{"lemmas": [...]}`. Saves as known (pos=None) via ManageKnownWordsUseCase.add_bulk(). |

### Async Build Mechanism

`POST /api/bootstrap/build` launches `BuildBootstrapIndexUseCase` via `asyncio.create_task(asyncio.to_thread(use_case.execute()))` — fire-and-forget, returns 202 immediately without awaiting completion. Repeated call while status=building → 409 Conflict.

## Frontend

### Settings Page — Calibration Block

State depends on `GET /api/bootstrap/status`:

| Status   | Display                                          |
|----------|--------------------------------------------------|
| none     | "Calibration data not prepared" + **Prepare** button |
| building | Spinner + "Preparing calibration data..." (poll every 2s) |
| error    | Error text + **Retry** button                    |
| ready    | "Ready — N words, built DD.MM.YYYY" + **Calibrate vocabulary** button + **Rebuild** (secondary) |

### Calibration Screen (route `/calibrate`)

- Up to 15 words displayed as clickable chips, randomly positioned (no visual CEFR/Zipf grouping)
- Click chip → toggled as "known" (highlighted). Click again → unmark.
- Default state: all unmarked ("don't know")
- Two buttons at bottom: **"Next N words"**, **"Finish"**

### React State

- `excludedLemmas: Set<string>` — all lemmas shown this session (grows across screens)
- `selectedLemmas: Set<string>` — marked on current screen (resets on next screen)
- `currentWords: BootstrapWordDTO[]` — current batch

### Flow

1. Open screen: `POST /api/bootstrap/words` with `{"excluded": []}` → receive first batch
2. User clicks words to toggle
3. **"Next N words"**: `POST /api/bootstrap/known` with selectedLemmas → add all currentWords to excludedLemmas → `POST /api/bootstrap/words` with updated excluded → reset selectedLemmas
4. **"Finish"**: `POST /api/bootstrap/known` with selectedLemmas → navigate back to `/settings`
5. If 0 words returned: show "All words reviewed", only **"Finish"** button

### Known Words — No POS

Words are displayed without POS. When saved as known: `add(lemma, pos=None)` — meaning the word is considered known for any POS.

### Writing to DB

Writes happen ONLY on "Next N words" or "Finish" — never during toggling. The user can safely click/unclick words without side effects until they explicitly advance.
