# Design: Manual Candidate Addition on Review Page

**Date:** 2026-04-05
**Status:** Approved

## Summary

Allow the user to manually add word candidates while reviewing a source. The user selects a phrase in the source text, clicks one or more words within that phrase as the target word(s), and the system creates a candidate using the same enrichment pipeline as automatic processing.

Multi-word targets are supported to handle phrasal verbs and split constructions (e.g. "look it up" → target = "look up").

## User Flow

1. User selects text in the right panel (source text area).
2. A floating popover appears above the selection.
3. The popover displays the selected phrase as individual clickable word tokens.
4. User clicks one or more tokens to mark them as the target word(s). Tokens highlight on click; clicking again deselects. Non-consecutive tokens are allowed.
5. "Add" button becomes active once at least one token is selected; user clicks it.
6. The new candidate appears at the top of the pending list in the left panel.
7. Popover closes; brief success toast confirms the addition.

**Target word construction:** selected tokens are sorted by their position in the phrase and joined with a space → `surface_form`. Example: "look" + "up" (non-consecutive) → `"look up"`.

**Edge cases:**
- Selection overlapping an existing candidate mark → popover not shown.
- Single word selected → auto-set as the only target token.
- SpaCy fails to lemmatize → use `surface_form` as `lemma`, `pos = "X"`.
- Duplicate candidates (same lemma already exists) → backend still creates; user decides.
- Escape or pointer-down outside → popover closes, nothing saved.

## Frontend

### New component: `SelectionPopover`

Props:
- `phrase: string` — the selected text
- `position: { x: number; y: number }` — anchor (from `getBoundingClientRect` of selection)
- `onAdd: (targetTokens: string[], contextFragment: string) => Promise<void>`
- `onClose: () => void`

Behaviour:
- Tokenises `phrase` into words and punctuation spans.
- Renders word tokens as clickable `<span>`; punctuation rendered as plain text (not clickable).
- Clicking a word token toggles its selected state (multi-select).
- Selected tokens highlighted with accent colour.
- "Add" button disabled until ≥1 token selected.
- Shows loading spinner on button while request is in-flight.
- Closes on Escape or pointer-down outside the popover.

Visual style: glass card (`var(--glass-b)` border, backdrop-blur), consistent with existing UI.

### Changes to `TextAnnotator`

- Add optional prop `onManualAdd?: (surfaceForm: string, contextFragment: string) => Promise<void>`.
- Listen for `mouseup` on the container div.
- On mouseup: read `window.getSelection()`. If selection is non-empty and lies within the container → extract the selected string as `contextFragment`, show `SelectionPopover`.
- If the selection intersects an existing `<mark>` element → do not show popover.
- When popover calls `onAdd(tokens, contextFragment)`: compute `surfaceForm = tokens sorted by position joined by space`, call `onManualAdd(surfaceForm, contextFragment)`.

### Changes to `ReviewPage`

- Add `handleManualAdd(surfaceForm, contextFragment)` callback:
  - Calls `api.addManualCandidate(sourceId, surfaceForm, contextFragment)`.
  - Prepends returned candidate to `candidates` state (after `sortCandidates`).
- Pass `onManualAdd` to `TextAnnotator`.
- Add `api.addManualCandidate` to the API client.

## Backend

### New use case: `AddManualCandidateUseCase`

Input: `source_id: int`, `surface_form: str`, `context_fragment: str`

Steps:
1. Load source; raise `SourceNotFoundError` if missing.
2. Analyse `surface_form` with `TextAnalyzer` to get `lemma` and `pos`. On failure: `lemma = surface_form.lower()`, `pos = "X"`.
3. Classify CEFR via `CefrClassifier`. May return `None`.
4. Get Zipf frequency via `FrequencyProvider`.
5. Compute `is_sweet_spot` via `CandidateFilter` — **no CEFR gate**: always save regardless of CEFR level.
6. Count `occurrences` of `surface_form` (case-insensitive) in `source.cleaned_text or source.raw_text`.
7. Detect `is_phrasal_verb` via `PhrasalVerbDetector` if `surface_form` contains a space.
8. Build `StoredCandidate` with `status=PENDING`, `fragment_purity="manual"`.
9. Persist via `CandidateRepository.save()`.
10. Return candidate as `StoredCandidateDTO`.

### New DTO: `AddManualCandidateRequest`

```python
class AddManualCandidateRequest(BaseModel):
    surface_form: str
    context_fragment: str
```

### New route

`POST /sources/{source_id}/candidates/manual`
Returns: existing `StoredCandidateDTO`.
Errors: 404 if source not found.

### No DB migration needed

`fragment_purity` column already exists; value `"manual"` requires no schema change.

## What is NOT changed

- Automatic processing pipeline — untouched.
- CEFR filtering in `CandidateFilter` — untouched (new use case bypasses the filter gate, not the filter itself).
- Existing candidate DTO — reused as-is.
- All existing tests — must remain green.

## Testing

- Unit: `AddManualCandidateUseCase` with mocked ports — normal path, SpaCy failure fallback, source-not-found.
- Integration: route test creating a manual candidate end-to-end.
