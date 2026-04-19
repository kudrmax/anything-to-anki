# Unify Candidate Sorting

**Date:** 2026-04-19
**Status:** Draft

## Problem

Two independent sorting implementations for candidates diverge:

1. **In-memory** (`analyze_text.py:242-249`): `is_phrasal_verb DESC, is_sweet_spot DESC, zipf ASC, occurrences DESC`
2. **SQL** (`sqla_candidate_repository.py:49-56`): `is_sweet_spot DESC, zipf DESC, cefr ASC`

Criteria don't match (different fields, opposite zipf direction). Additionally, CHRONOLOGICAL sorting logic (`text.find(context_fragment)`) is duplicated across 4 use cases. Both violations: business logic in infrastructure layer and duplicated across application layer.

## Design

### 1. FrequencyBand enum replaces continuous zipf sorting

Current `FrequencyBand` is a dataclass wrapping a float. Replace with an enum of 5 discrete bands.

```python
# domain/value_objects/frequency_band.py

class FrequencyBand(Enum):
    ULTRA_COMMON = 5  # zipf >= 5.5
    COMMON = 4        # 4.5 <= zipf < 5.5
    MID = 3           # 3.5 <= zipf < 4.5  (replaces "sweet spot")
    LOW = 2           # 2.5 <= zipf < 3.5
    RARE = 1          # zipf < 2.5

    @classmethod
    def from_zipf(cls, zipf: float) -> FrequencyBand:
        if zipf >= 5.5:
            return cls.ULTRA_COMMON
        if zipf >= 4.5:
            return cls.COMMON
        if zipf >= 3.5:
            return cls.MID
        if zipf >= 2.5:
            return cls.LOW
        return cls.RARE
```

Enum values (5, 4, 3, 2, 1) are chosen so that sorting by value descending = frequent-to-rare order.

### 2. StoredCandidate entity changes

- **Remove** field `is_sweet_spot: bool` — it becomes derived.
- **Add** computed property `frequency_band -> FrequencyBand` from `zipf_frequency`.
- **Add** computed property `is_sweet_spot -> bool` as `frequency_band == FrequencyBand.MID`.

### 3. Single sorting service in domain layer

```python
# domain/services/candidate_sorting.py

def sort_by_relevance(candidates: list[StoredCandidate]) -> list[StoredCandidate]:
    """Canonical RELEVANCE sort order:
    1. frequency_band DESC — more frequent bands first
    2. is_phrasal_verb DESC — phrasal verbs first within same band
    3. cefr_level ASC — easier levels first; None sorts after C2
    4. occurrences DESC — more occurrences in source text first
    """

def sort_chronologically(
    candidates: list[StoredCandidate],
    source_text: str,
) -> list[StoredCandidate]:
    """Sort by position of context_fragment in source_text.
    Tiebreaker: candidate id (insertion order).
    """
```

### 4. Remove sorting from infrastructure and application layers

**Infrastructure (repositories):**
- `sqla_candidate_repository.py` — remove `order_by` for RELEVANCE. Return without ordering guarantees.
- `sqla_candidate_meaning_repository.py` — remove `order_by` for RELEVANCE/CHRONOLOGICAL.
- `sqla_candidate_media_repository.py` — remove `order_by` for RELEVANCE/CHRONOLOGICAL.
- Repositories no longer accept `sort_order` parameter. They return candidates unsorted.

**Application (use cases):**
- `analyze_text.py` — remove inline `.sort()` (lines 242-249). Sorting is not needed at analysis time; it applies when candidates are fetched for display.
- `get_candidates.py`, `get_sources.py`, `enqueue_meaning_generation.py`, `enqueue_media_generation.py` — replace inline chronological sorting logic with call to `sort_chronologically()` from domain service.
- All use cases call `sort_by_relevance()` or `sort_chronologically()` from the domain service instead of implementing their own sorting.

### 5. CandidateSortOrder — unchanged

```python
class CandidateSortOrder(Enum):
    RELEVANCE = "relevance"
    CHRONOLOGICAL = "chronological"
```

Stays in domain. Use cases map this enum to the appropriate domain sort function.

### 6. Database — no migration

- Column `is_sweet_spot` in `candidates` table stays. We stop reading/writing it (effectively dead column). Can be removed in a future migration.
- `zipf_frequency` float column stays — the band is always computed from it at read time.

### 7. DTOs

- `is_sweet_spot` field stays in `WordCandidateDTO` and `StoredCandidateDTO`. Computed as `frequency_band == MID` when building the DTO.
- Frontend receives `is_sweet_spot` as before, no frontend changes needed.

### 8. CEFR sort order for None values

CEFR levels sort: A1 < A2 < B1 < B2 < C1 < C2 < None. Candidates without CEFR data go to the bottom within their band.

### 9. UI

`is_sweet_spot` badge in UI now highlights MID-band words (was 3.0-4.5, now 3.5-4.5). No UI code changes — only the backend computation changes.

## Files to change

| File | Change |
|------|--------|
| `domain/value_objects/frequency_band.py` | Rewrite: dataclass -> enum with `from_zipf()` |
| `domain/entities/stored_candidate.py` | Remove `is_sweet_spot` field, add `frequency_band` and `is_sweet_spot` properties |
| `domain/services/candidate_sorting.py` | **New file**: `sort_by_relevance()`, `sort_chronologically()` |
| `domain/ports/candidate_repository.py` | Remove `sort_order` param from `get_by_source()` |
| `domain/ports/candidate_meaning_repository.py` | Remove `sort_order` param if present |
| `domain/ports/candidate_media_repository.py` | Remove `sort_order` param if present |
| `infrastructure/persistence/sqla_candidate_repository.py` | Remove all `order_by`, remove `sort_order` param |
| `infrastructure/persistence/sqla_candidate_meaning_repository.py` | Remove `order_by`, remove `sort_order` param |
| `infrastructure/persistence/sqla_candidate_media_repository.py` | Remove `order_by`, remove `sort_order` param |
| `infrastructure/persistence/models.py` | `from_entity()`: stop writing `is_sweet_spot`. `to_entity()`: stop reading `is_sweet_spot` |
| `application/use_cases/analyze_text.py` | Remove inline sort (lines 242-249), remove old `FrequencyBand` usage |
| `application/use_cases/get_candidates.py` | Use domain sort service |
| `application/use_cases/get_sources.py` | Use domain sort service |
| `application/use_cases/enqueue_meaning_generation.py` | Use domain sort service |
| `application/use_cases/enqueue_media_generation.py` | Use domain sort service |
| `application/use_cases/process_source.py` | Remove `is_sweet_spot` from `StoredCandidate` construction |
| `application/use_cases/add_manual_candidate.py` | Remove `is_sweet_spot` from `StoredCandidate` construction |
| `application/use_cases/replace_with_example.py` | Remove `is_sweet_spot` from `StoredCandidate` construction |
| `application/dto/analysis_dtos.py` | Keep `is_sweet_spot`, compute from band |
| `application/dto/source_dtos.py` | Keep `is_sweet_spot`, compute from band |
| Tests (unit + integration) | Update fixtures, add sort service tests |

## Out of scope

- Removing `is_sweet_spot` DB column (future migration)
- Changing frequency band boundaries (can be tuned later)
- Frontend changes
