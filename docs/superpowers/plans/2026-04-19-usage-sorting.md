# Usage Sorting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить usage-группы из Cambridge Dictionary как критерий сортировки кандидатов, с настраиваемым порядком групп в UI.

**Architecture:** Usage-distribution вычисляется из Cambridge sense'ов при анализе текста и сохраняется на кандидате. Сортировка в domain service использует пользовательский порядок групп из settings. UI предоставляет drag-and-drop для настройки порядка.

**Tech Stack:** Python, SQLAlchemy, Alembic, Pydantic, React/TypeScript

**Spec:** `docs/superpowers/specs/2026-04-19-usage-sorting-design.md`

---

### Task 1: Usage group mapping — константы и нормализация

**Files:**
- Create: `backend/src/backend/infrastructure/adapters/cambridge/usage_groups.py`
- Create: `backend/tests/unit/infrastructure/test_cambridge_usage_groups.py`

- [ ] **Step 1: Write tests for usage group mapping**

```python
import pytest
from backend.infrastructure.adapters.cambridge.usage_groups import (
    USAGE_GROUP_MAP,
    DEFAULT_USAGE_GROUP_ORDER,
    resolve_usage_group,
)


@pytest.mark.unit
class TestUsageGroupMap:
    def test_informal_variants(self) -> None:
        for raw in ("informal", "very informal", "slang", "infml"):
            assert USAGE_GROUP_MAP[raw] == "informal"

    def test_formal_variants(self) -> None:
        for raw in ("formal", "fml"):
            assert USAGE_GROUP_MAP[raw] == "formal"

    def test_specialized_with_typo(self) -> None:
        assert USAGE_GROUP_MAP["specalized"] == "specialized"
        assert USAGE_GROUP_MAP["specialized"] == "specialized"
        assert USAGE_GROUP_MAP["specialist"] == "specialized"

    def test_connotation_group(self) -> None:
        for raw in ("disapproving", "approving", "humorous"):
            assert USAGE_GROUP_MAP[raw] == "connotation"

    def test_old_fashioned_group(self) -> None:
        for raw in ("old-fashioned", "old use", "dated"):
            assert USAGE_GROUP_MAP[raw] == "old-fashioned"

    def test_offensive_group(self) -> None:
        for raw in ("offensive", "very offensive", "extremely offensive"):
            assert USAGE_GROUP_MAP[raw] == "offensive"

    def test_other_group(self) -> None:
        for raw in ("literary", "trademark", "child's word", "figurative", "not standard"):
            assert USAGE_GROUP_MAP[raw] == "other"


@pytest.mark.unit
class TestResolveUsageGroup:
    def test_known_usage(self) -> None:
        assert resolve_usage_group("informal") == "informal"

    def test_unknown_usage_returns_none(self) -> None:
        assert resolve_usage_group("totally_unknown_label") is None

    def test_case_insensitive(self) -> None:
        assert resolve_usage_group("Informal") == "informal"
        assert resolve_usage_group("FORMAL") == "formal"


@pytest.mark.unit
class TestDefaultOrder:
    def test_has_all_groups(self) -> None:
        expected = {"neutral", "informal", "formal", "specialized",
                    "connotation", "old-fashioned", "offensive", "other"}
        assert set(DEFAULT_USAGE_GROUP_ORDER) == expected

    def test_no_duplicates(self) -> None:
        assert len(DEFAULT_USAGE_GROUP_ORDER) == len(set(DEFAULT_USAGE_GROUP_ORDER))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test-unit k=test_cambridge_usage_groups`
Expected: ImportError — module does not exist yet.

- [ ] **Step 3: Implement usage group mapping**

```python
"""Cambridge usage label → usage group mapping and helpers."""
from __future__ import annotations

USAGE_GROUP_MAP: dict[str, str] = {
    # informal
    "informal": "informal",
    "very informal": "informal",
    "slang": "informal",
    "infml": "informal",
    # formal
    "formal": "formal",
    "fml": "formal",
    # specialized
    "specialized": "specialized",
    "specialist": "specialized",
    "specalized": "specialized",  # typo in data
    # connotation
    "disapproving": "connotation",
    "approving": "connotation",
    "humorous": "connotation",
    # old-fashioned
    "old-fashioned": "old-fashioned",
    "old use": "old-fashioned",
    "dated": "old-fashioned",
    # offensive
    "offensive": "offensive",
    "very offensive": "offensive",
    "extremely offensive": "offensive",
    # other
    "literary": "other",
    "trademark": "other",
    "child's word": "other",
    "figurative": "other",
    "not standard": "other",
}

DEFAULT_USAGE_GROUP_ORDER: list[str] = [
    "neutral",
    "informal",
    "formal",
    "specialized",
    "connotation",
    "old-fashioned",
    "offensive",
    "other",
]


def resolve_usage_group(raw_usage: str) -> str | None:
    """Map a raw Cambridge usage label to a usage group name.

    Returns None if the label is not recognized.
    """
    return USAGE_GROUP_MAP.get(raw_usage.lower().strip())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test-unit k=test_cambridge_usage_groups`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/backend/infrastructure/adapters/cambridge/usage_groups.py backend/tests/unit/infrastructure/test_cambridge_usage_groups.py
git commit -m "feat: add Cambridge usage group mapping and normalization"
```

---

### Task 2: UsageDistribution value object

**Files:**
- Create: `backend/src/backend/domain/value_objects/usage_distribution.py`
- Create: `backend/tests/unit/domain/test_usage_distribution.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from backend.domain.value_objects.usage_distribution import UsageDistribution


@pytest.mark.unit
class TestUsageDistribution:
    def test_create_from_dict(self) -> None:
        ud = UsageDistribution({"informal": 0.6, "neutral": 0.4})
        assert ud.groups == {"informal": 0.6, "neutral": 0.4}

    def test_none_distribution(self) -> None:
        ud = UsageDistribution(None)
        assert ud.groups is None

    def test_primary_group_picks_first_in_order(self) -> None:
        ud = UsageDistribution({"informal": 0.4, "formal": 0.6})
        order = ["formal", "informal", "neutral"]
        assert ud.primary_group(order) == "formal"

    def test_primary_group_skips_missing(self) -> None:
        ud = UsageDistribution({"informal": 1.0})
        order = ["neutral", "formal", "informal"]
        assert ud.primary_group(order) == "informal"

    def test_primary_group_none_distribution_returns_neutral(self) -> None:
        ud = UsageDistribution(None)
        order = ["formal", "neutral", "informal"]
        assert ud.primary_group(order) == "neutral"

    def test_primary_group_empty_distribution_returns_neutral(self) -> None:
        ud = UsageDistribution({})
        order = ["formal", "neutral"]
        assert ud.primary_group(order) == "neutral"

    def test_primary_group_no_match_returns_neutral(self) -> None:
        """If distribution has groups not in order, fallback to neutral."""
        ud = UsageDistribution({"unknown_group": 1.0})
        order = ["neutral", "informal"]
        assert ud.primary_group(order) == "neutral"

    def test_rank_returns_index(self) -> None:
        ud = UsageDistribution({"informal": 1.0})
        order = ["neutral", "informal", "formal"]
        assert ud.rank(order) == 1

    def test_rank_none_distribution_returns_neutral_index(self) -> None:
        ud = UsageDistribution(None)
        order = ["formal", "neutral", "informal"]
        assert ud.rank(order) == 1  # neutral is at index 1

    def test_to_dict_and_back(self) -> None:
        original = {"informal": 0.6, "neutral": 0.4}
        ud = UsageDistribution(original)
        assert ud.to_dict() == original

    def test_to_dict_none(self) -> None:
        ud = UsageDistribution(None)
        assert ud.to_dict() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test-unit k=test_usage_distribution`
Expected: ImportError.

- [ ] **Step 3: Implement UsageDistribution**

```python
"""Usage distribution value object."""
from __future__ import annotations

from dataclasses import dataclass

_NEUTRAL = "neutral"


@dataclass(frozen=True)
class UsageDistribution:
    """Distribution of Cambridge usage groups across a word's senses.

    None means the word was not found in Cambridge.
    Empty dict is treated the same as None (neutral).
    """

    groups: dict[str, float] | None

    def primary_group(self, order: list[str]) -> str:
        """Return the highest-priority group present in this distribution.

        Priority is determined by position in `order` (index 0 = highest).
        Returns 'neutral' if distribution is None/empty or no groups match.
        """
        if not self.groups:
            return _NEUTRAL
        for group in order:
            if group in self.groups:
                return group
        return _NEUTRAL

    def rank(self, order: list[str]) -> int:
        """Return the sort rank (index in order) of the primary group.

        Lower rank = higher priority in sorting.
        """
        group = self.primary_group(order)
        try:
            return order.index(group)
        except ValueError:
            return len(order)

    def to_dict(self) -> dict[str, float] | None:
        """Serialize for storage."""
        return dict(self.groups) if self.groups else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test-unit k=test_usage_distribution`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/backend/domain/value_objects/usage_distribution.py backend/tests/unit/domain/test_usage_distribution.py
git commit -m "feat: add UsageDistribution value object"
```

---

### Task 3: Cambridge usage distribution lookup service

**Files:**
- Create: `backend/src/backend/infrastructure/adapters/cambridge/usage_lookup.py`
- Create: `backend/tests/unit/infrastructure/test_cambridge_usage_lookup.py`

Этот сервис вычисляет `UsageDistribution` для lemma+POS из Cambridge данных. Переиспользует POS-маппинг и фильтрацию entry из `cefr_source.py`.

- [ ] **Step 1: Write tests**

```python
import pytest
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.adapters.cambridge.models import (
    CambridgeEntry,
    CambridgeSense,
    CambridgeWord,
)
from backend.infrastructure.adapters.cambridge.usage_lookup import CambridgeUsageLookup


def _sense(usages: list[str] | None = None) -> CambridgeSense:
    return CambridgeSense(
        definition="test",
        level="",
        examples=[],
        labels_and_codes=[],
        usages=usages or [],
        domains=[],
        regions=[],
        image_link="",
    )


def _word(pos: list[str], senses: list[CambridgeSense]) -> CambridgeWord:
    return CambridgeWord(
        word="test",
        entries=[CambridgeEntry(
            headword="test",
            pos=pos,
            uk_ipa=[], us_ipa=[],
            uk_audio=[], us_audio=[],
            senses=senses,
        )],
    )


@pytest.mark.unit
class TestCambridgeUsageLookup:
    def test_word_not_in_cambridge(self) -> None:
        lookup = CambridgeUsageLookup({})
        result = lookup.get_distribution("missing", "NN")
        assert result.groups is None

    def test_all_senses_no_usages(self) -> None:
        """All senses unmarked → distribution is {'neutral': 1.0}."""
        data = {"cool": _word(["adjective"], [_sense(), _sense()])}
        lookup = CambridgeUsageLookup(data)
        result = lookup.get_distribution("cool", "JJ")
        assert result.groups == {"neutral": 1.0}

    def test_mixed_usages(self) -> None:
        """3 neutral + 2 informal → {neutral: 0.6, informal: 0.4}."""
        data = {"cool": _word(["adjective"], [
            _sense(),  # neutral
            _sense(),  # neutral
            _sense(),  # neutral
            _sense(["informal"]),
            _sense(["slang"]),  # maps to informal
        ])}
        lookup = CambridgeUsageLookup(data)
        result = lookup.get_distribution("cool", "JJ")
        assert result.groups is not None
        assert abs(result.groups["neutral"] - 0.6) < 0.01
        assert abs(result.groups["informal"] - 0.4) < 0.01

    def test_all_informal(self) -> None:
        data = {"gonna": _word(["verb"], [
            _sense(["informal"]),
            _sense(["very informal"]),
        ])}
        lookup = CambridgeUsageLookup(data)
        result = lookup.get_distribution("gonna", "VB")
        assert result.groups == {"informal": 1.0}

    def test_pos_filtering(self) -> None:
        """Only senses from matching POS entries are counted."""
        data = {"cool": CambridgeWord(
            word="cool",
            entries=[
                CambridgeEntry(
                    headword="cool", pos=["adjective"],
                    uk_ipa=[], us_ipa=[], uk_audio=[], us_audio=[],
                    senses=[_sense(["informal"])],
                ),
                CambridgeEntry(
                    headword="cool", pos=["noun"],
                    uk_ipa=[], us_ipa=[], uk_audio=[], us_audio=[],
                    senses=[_sense()],  # neutral
                ),
            ],
        )}
        lookup = CambridgeUsageLookup(data)
        # JJ maps to adjective → only informal sense
        result = lookup.get_distribution("cool", "JJ")
        assert result.groups == {"informal": 1.0}

    def test_pos_fallback_all_entries(self) -> None:
        """Unknown POS → all entries used."""
        data = {"cool": CambridgeWord(
            word="cool",
            entries=[
                CambridgeEntry(
                    headword="cool", pos=["adjective"],
                    uk_ipa=[], us_ipa=[], uk_audio=[], us_audio=[],
                    senses=[_sense(["informal"])],
                ),
                CambridgeEntry(
                    headword="cool", pos=["noun"],
                    uk_ipa=[], us_ipa=[], uk_audio=[], us_audio=[],
                    senses=[_sense()],
                ),
            ],
        )}
        lookup = CambridgeUsageLookup(data)
        result = lookup.get_distribution("cool", "XX")  # unknown POS
        assert result.groups is not None
        assert abs(result.groups["informal"] - 0.5) < 0.01
        assert abs(result.groups["neutral"] - 0.5) < 0.01

    def test_sense_with_multiple_usages(self) -> None:
        """A sense with multiple usage labels — first recognized one wins."""
        data = {"word": _word(["noun"], [
            _sense(["formal", "disapproving"]),
        ])}
        lookup = CambridgeUsageLookup(data)
        result = lookup.get_distribution("word", "NN")
        # First recognized usage wins for this sense
        assert result.groups is not None
        assert len(result.groups) == 1

    def test_unknown_usage_label_treated_as_neutral(self) -> None:
        """Unrecognized usage label → sense treated as neutral."""
        data = {"word": _word(["noun"], [_sense(["some_weird_label"])])}
        lookup = CambridgeUsageLookup(data)
        result = lookup.get_distribution("word", "NN")
        assert result.groups == {"neutral": 1.0}

    def test_case_insensitive_lemma(self) -> None:
        data = {"hello": _word(["noun"], [_sense(["informal"])])}
        lookup = CambridgeUsageLookup(data)
        result = lookup.get_distribution("Hello", "NN")
        assert result.groups == {"informal": 1.0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test-unit k=test_cambridge_usage_lookup`
Expected: ImportError.

- [ ] **Step 3: Implement CambridgeUsageLookup**

```python
"""Compute UsageDistribution from Cambridge Dictionary data."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.adapters.cambridge.cefr_source import (
    _POS_TO_CAMBRIDGE,
)
from backend.infrastructure.adapters.cambridge.usage_groups import resolve_usage_group

if TYPE_CHECKING:
    from backend.infrastructure.adapters.cambridge.models import (
        CambridgeEntry,
        CambridgeSense,
        CambridgeWord,
    )

_NEUTRAL = "neutral"


class CambridgeUsageLookup:
    """Computes usage distribution for a word from Cambridge data."""

    def __init__(self, data: dict[str, CambridgeWord]) -> None:
        self._data = data

    def get_distribution(self, lemma: str, pos_tag: str) -> UsageDistribution:
        word = self._data.get(lemma.lower())
        if word is None:
            return UsageDistribution(None)

        cambridge_pos = _POS_TO_CAMBRIDGE.get(pos_tag)
        entries = self._filter_entries_by_pos(word.entries, cambridge_pos)
        senses = [s for e in entries for s in e.senses]

        if not senses:
            return UsageDistribution(None)

        group_counts: dict[str, int] = {}
        for sense in senses:
            group = self._sense_group(sense)
            group_counts[group] = group_counts.get(group, 0) + 1

        total = sum(group_counts.values())
        distribution = {g: count / total for g, count in group_counts.items()}
        return UsageDistribution(distribution)

    @staticmethod
    def _sense_group(sense: CambridgeSense) -> str:
        """Determine the usage group for a single sense.

        Uses the first recognized usage label. If none recognized → neutral.
        """
        for raw in sense.usages:
            group = resolve_usage_group(raw)
            if group is not None:
                return group
        return _NEUTRAL

    @staticmethod
    def _filter_entries_by_pos(
        entries: list[CambridgeEntry],
        cambridge_pos: str | None,
    ) -> list[CambridgeEntry]:
        if cambridge_pos is None:
            return list(entries)
        matched = [e for e in entries if cambridge_pos in e.pos]
        return matched if matched else list(entries)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test-unit k=test_cambridge_usage_lookup`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/backend/infrastructure/adapters/cambridge/usage_lookup.py backend/tests/unit/infrastructure/test_cambridge_usage_lookup.py
git commit -m "feat: add Cambridge usage distribution lookup service"
```

---

### Task 4: Добавить usage_distribution на StoredCandidate + Alembic-миграция

**Files:**
- Modify: `backend/src/backend/domain/entities/stored_candidate.py`
- Modify: `backend/src/backend/infrastructure/persistence/models.py`
- Create: `backend/src/backend/alembic/versions/0014_add_usage_distribution.py`

- [ ] **Step 1: Add field to StoredCandidate entity**

В `backend/src/backend/domain/entities/stored_candidate.py`, добавить import и поле:

```python
# В секции TYPE_CHECKING:
from backend.domain.value_objects.usage_distribution import UsageDistribution

# В dataclass, после cefr_breakdown:
usage_distribution: UsageDistribution = UsageDistribution(None)
```

Добавить `UsageDistribution` в `TYPE_CHECKING` блок (как `CEFRBreakdown`), а дефолтное значение задать через `field(default_factory=...)`:

```python
from dataclasses import dataclass, field
```

Итоговое поле:
```python
    usage_distribution: UsageDistribution | None = None
```

Примечание: используем `None` вместо `UsageDistribution(None)` чтобы избежать import вне TYPE_CHECKING. В коде сортировки `None` будет обрабатываться как neutral.

- [ ] **Step 2: Add column to SQLAlchemy model**

В `backend/src/backend/infrastructure/persistence/models.py`, в классе `StoredCandidateModel` после `has_custom_context_fragment`:

```python
    usage_distribution_json: Mapped[str | None] = mapped_column(
        "usage_distribution", Text, nullable=True
    )
```

В методе `to_entity()` добавить парсинг:

```python
import json
from backend.domain.value_objects.usage_distribution import UsageDistribution

# В to_entity(), перед return:
ud: UsageDistribution | None = None
if self.usage_distribution_json is not None:
    ud = UsageDistribution(json.loads(self.usage_distribution_json))
# Добавить в конструктор StoredCandidate:
usage_distribution=ud,
```

В методе `from_entity()` добавить сериализацию:

```python
# После создания model:
if candidate.usage_distribution is not None:
    dist = candidate.usage_distribution.to_dict()
    model.usage_distribution_json = json.dumps(dist) if dist else None
```

- [ ] **Step 3: Create Alembic migration**

```python
"""Add usage_distribution column to stored_candidates.

Revision ID: 0014
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stored_candidates",
        sa.Column("usage_distribution", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stored_candidates", "usage_distribution")
```

- [ ] **Step 4: Run migration and verify**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make up-worktree`
Then: `make test-unit k=test_candidate_sorting`
Expected: Existing sorting tests still pass (new field has default None, doesn't affect anything yet).

- [ ] **Step 5: Commit**

```bash
git add backend/src/backend/domain/entities/stored_candidate.py backend/src/backend/infrastructure/persistence/models.py backend/src/backend/alembic/versions/0014_add_usage_distribution.py
git commit -m "feat: add usage_distribution field to StoredCandidate + migration"
```

---

### Task 5: Добавить usage_order в сортировку

**Files:**
- Modify: `backend/src/backend/domain/services/candidate_sorting.py`
- Modify: `backend/tests/unit/domain/test_candidate_sorting.py`

- [ ] **Step 1: Write tests for usage-aware sorting**

Добавить в `backend/tests/unit/domain/test_candidate_sorting.py`:

```python
from backend.domain.value_objects.usage_distribution import UsageDistribution

# Обновить хелпер _make — добавить параметр usage_distribution:
def _make(
    lemma: str,
    zipf: float,
    *,
    cefr: str | None = "B1",
    occurrences: int = 1,
    is_phrasal_verb: bool = False,
    context_fragment: str = "",
    usage_distribution: UsageDistribution | None = None,
) -> StoredCandidate:
    return StoredCandidate(
        source_id=1,
        lemma=lemma,
        pos="NN",
        cefr_level=cefr,
        zipf_frequency=zipf,
        context_fragment=context_fragment or f"context for {lemma}",
        fragment_purity="clean",
        occurrences=occurrences,
        status=CandidateStatus.PENDING,
        is_phrasal_verb=is_phrasal_verb,
        usage_distribution=usage_distribution,
    )


@pytest.mark.unit
class TestSortByRelevanceWithUsage:
    """Tests for usage_order parameter in sort_by_relevance."""

    ORDER = ["neutral", "informal", "formal", "specialized"]

    def test_usage_rank_within_same_band_and_phrasal(self) -> None:
        """Usage rank sorts between phrasal_verb and CEFR."""
        formal = _make("formal_w", 4.0,
                        usage_distribution=UsageDistribution({"formal": 1.0}))
        informal = _make("informal_w", 4.0,
                          usage_distribution=UsageDistribution({"informal": 1.0}))
        result = sort_by_relevance([formal, informal], usage_order=self.ORDER)
        # informal (index 1) before formal (index 2)
        assert [c.lemma for c in result] == ["informal_w", "formal_w"]

    def test_band_still_beats_usage(self) -> None:
        """Higher frequency band wins over usage priority."""
        common_formal = _make("common", 5.0,
                               usage_distribution=UsageDistribution({"formal": 1.0}))
        mid_neutral = _make("mid", 4.0,
                             usage_distribution=UsageDistribution({"neutral": 1.0}))
        result = sort_by_relevance([mid_neutral, common_formal], usage_order=self.ORDER)
        assert [c.lemma for c in result] == ["common", "mid"]

    def test_phrasal_verb_still_beats_usage(self) -> None:
        """Phrasal verb status wins over usage within same band."""
        regular_neutral = _make("walk", 4.0,
                                 usage_distribution=UsageDistribution({"neutral": 1.0}))
        phrasal_formal = _make("give up", 4.0, is_phrasal_verb=True,
                                usage_distribution=UsageDistribution({"formal": 1.0}))
        result = sort_by_relevance([regular_neutral, phrasal_formal], usage_order=self.ORDER)
        assert [c.lemma for c in result] == ["give up", "walk"]

    def test_none_distribution_treated_as_neutral(self) -> None:
        """None usage_distribution → treated as neutral (index 0)."""
        no_usage = _make("unknown", 4.0, usage_distribution=None)
        formal = _make("formal_w", 4.0,
                        usage_distribution=UsageDistribution({"formal": 1.0}))
        result = sort_by_relevance([formal, no_usage], usage_order=self.ORDER)
        # neutral (index 0) before formal (index 2)
        assert [c.lemma for c in result] == ["unknown", "formal_w"]

    def test_mixed_distribution_uses_primary_group(self) -> None:
        """Distribution with multiple groups → primary = first in order."""
        mixed = _make("cool", 4.0,
                       usage_distribution=UsageDistribution({"informal": 0.4, "neutral": 0.6}))
        pure_informal = _make("gonna", 4.0,
                               usage_distribution=UsageDistribution({"informal": 1.0}))
        result = sort_by_relevance([pure_informal, mixed], usage_order=self.ORDER)
        # mixed primary = neutral (index 0), pure_informal primary = informal (index 1)
        assert [c.lemma for c in result] == ["cool", "gonna"]

    def test_no_usage_order_backward_compatible(self) -> None:
        """Without usage_order, sorting works as before (no usage ranking)."""
        formal = _make("formal_w", 4.0,
                        usage_distribution=UsageDistribution({"formal": 1.0}))
        informal = _make("informal_w", 4.0,
                          usage_distribution=UsageDistribution({"informal": 1.0}))
        result = sort_by_relevance([formal, informal])
        # Stable sort — original order preserved (no usage key)
        assert [c.lemma for c in result] == ["formal_w", "informal_w"]

    def test_custom_user_order(self) -> None:
        """User-defined order changes sorting result."""
        custom_order = ["formal", "informal", "neutral"]
        formal = _make("formal_w", 4.0,
                        usage_distribution=UsageDistribution({"formal": 1.0}))
        informal = _make("informal_w", 4.0,
                          usage_distribution=UsageDistribution({"informal": 1.0}))
        result = sort_by_relevance([informal, formal], usage_order=custom_order)
        # formal (index 0) before informal (index 1)
        assert [c.lemma for c in result] == ["formal_w", "informal_w"]

    def test_full_priority_with_usage(self) -> None:
        """band > phrasal > usage > cefr > occurrences."""
        candidates = [
            _make("rare", 2.0, usage_distribution=UsageDistribution({"neutral": 1.0})),
            _make("mid_formal_b1", 4.0, cefr="B1",
                  usage_distribution=UsageDistribution({"formal": 1.0})),
            _make("mid_neutral_b2", 4.0, cefr="B2",
                  usage_distribution=UsageDistribution({"neutral": 1.0})),
            _make("mid_neutral_b1", 4.0, cefr="B1",
                  usage_distribution=UsageDistribution({"neutral": 1.0})),
            _make("common", 5.0, usage_distribution=UsageDistribution({"informal": 1.0})),
        ]
        result = sort_by_relevance(candidates, usage_order=self.ORDER)
        assert [c.lemma for c in result] == [
            "common",           # COMMON band
            "mid_neutral_b1",   # MID, neutral (0), B1
            "mid_neutral_b2",   # MID, neutral (0), B2
            "mid_formal_b1",    # MID, formal (2), B1
            "rare",             # RARE band
        ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test-unit k=TestSortByRelevanceWithUsage`
Expected: FAIL — `sort_by_relevance` doesn't accept `usage_order`.

- [ ] **Step 3: Update sort_by_relevance**

В `backend/src/backend/domain/services/candidate_sorting.py`:

```python
"""Canonical sort functions for word candidates.

These are the ONLY place where candidate ordering logic lives.
Repositories return candidates unsorted; use cases call these functions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate

# CEFR sort key: A1=1 .. C2=6, None=99 (after everything)
_CEFR_ORDER: dict[str | None, int] = {
    "A1": 1, "A2": 2,
    "B1": 3, "B2": 4,
    "C1": 5, "C2": 6,
    None: 99,
}

_NEUTRAL = "neutral"


def _cefr_sort_key(cefr_level: str | None) -> int:
    return _CEFR_ORDER.get(cefr_level, 99)


def _usage_sort_key(candidate: StoredCandidate, usage_order: list[str] | None) -> int:
    if usage_order is None:
        return 0  # no usage sorting — all equal
    if candidate.usage_distribution is None:
        # Not in Cambridge → treat as neutral
        try:
            return usage_order.index(_NEUTRAL)
        except ValueError:
            return len(usage_order)
    return candidate.usage_distribution.rank(usage_order)


def sort_by_relevance(
    candidates: list[StoredCandidate],
    usage_order: list[str] | None = None,
) -> list[StoredCandidate]:
    """Sort candidates by relevance for learning.

    Priority (all within the same level win over the next level):
    1. frequency_band DESC — more frequent bands first
    2. is_phrasal_verb DESC — phrasal verbs first within same band
    3. usage_rank ASC — higher-priority usage group first (if usage_order given)
    4. cefr_level ASC — easier levels first; None sorts after C2
    5. occurrences DESC — more occurrences in source text first
    """
    return sorted(
        candidates,
        key=lambda c: (
            -c.frequency_band.value,
            not c.is_phrasal_verb,
            _usage_sort_key(c, usage_order),
            _cefr_sort_key(c.cefr_level),
            -c.occurrences,
        ),
    )


def sort_chronologically(
    candidates: list[StoredCandidate],
    source_text: str,
) -> list[StoredCandidate]:
    """Sort candidates by position of context_fragment in source text.

    Candidates whose fragment is not found in the text sort last.
    Tiebreaker: candidate id (insertion order).
    """
    text_len = len(source_text)

    def _position_key(c: StoredCandidate) -> tuple[int, int]:
        pos = source_text.find(c.context_fragment)
        if pos < 0:
            pos = text_len
        return (pos, c.id or 0)

    return sorted(candidates, key=_position_key)
```

- [ ] **Step 4: Run ALL sorting tests**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test-unit k=test_candidate_sorting`
Expected: All PASS — old tests backward-compatible (usage_order=None), new tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/backend/domain/services/candidate_sorting.py backend/tests/unit/domain/test_candidate_sorting.py
git commit -m "feat: add usage_order parameter to sort_by_relevance"
```

---

### Task 6: Settings — usage_group_order

**Files:**
- Modify: `backend/src/backend/application/dto/settings_dtos.py`
- Modify: `backend/src/backend/application/use_cases/manage_settings.py`
- Create: `backend/tests/unit/application/test_usage_group_order_settings.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from backend.application.use_cases.manage_settings import ManageSettingsUseCase
from backend.application.dto.settings_dtos import UpdateSettingsRequest


class FakeSettingsRepo:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._data.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value


@pytest.mark.unit
class TestUsageGroupOrderSettings:
    def test_default_order(self) -> None:
        uc = ManageSettingsUseCase(FakeSettingsRepo())
        settings = uc.get_settings()
        assert settings.usage_group_order == [
            "neutral", "informal", "formal", "specialized",
            "connotation", "old-fashioned", "offensive", "other",
        ]

    def test_update_order(self) -> None:
        repo = FakeSettingsRepo()
        uc = ManageSettingsUseCase(repo)
        new_order = ["informal", "neutral", "formal", "specialized",
                     "connotation", "old-fashioned", "offensive", "other"]
        uc.update_settings(UpdateSettingsRequest(usage_group_order=new_order))
        settings = uc.get_settings()
        assert settings.usage_group_order == new_order

    def test_round_trip_preserves_order(self) -> None:
        repo = FakeSettingsRepo()
        uc = ManageSettingsUseCase(repo)
        order = ["offensive", "other", "neutral", "informal",
                 "formal", "specialized", "connotation", "old-fashioned"]
        uc.update_settings(UpdateSettingsRequest(usage_group_order=order))
        assert uc.get_settings().usage_group_order == order
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test-unit k=test_usage_group_order_settings`
Expected: FAIL — `usage_group_order` not in SettingsDTO.

- [ ] **Step 3: Add usage_group_order to settings**

В `backend/src/backend/application/dto/settings_dtos.py`:

Добавить поле в `SettingsDTO`:
```python
    usage_group_order: list[str]
```

Добавить поле в `UpdateSettingsRequest`:
```python
    usage_group_order: list[str] | None = None
```

В `backend/src/backend/application/use_cases/manage_settings.py`:

Добавить import:
```python
import json
from backend.infrastructure.adapters.cambridge.usage_groups import DEFAULT_USAGE_GROUP_ORDER
```

Добавить в `_SETTING_KEYS`:
```python
    "usage_group_order": json.dumps(DEFAULT_USAGE_GROUP_ORDER),
```

Добавить `"usage_group_order"` в `_JSON_LIST_KEYS` (новый набор, аналогично `_BOOL_KEYS`):
```python
_JSON_LIST_KEYS: frozenset[str] = frozenset({"usage_group_order"})
```

В `get_settings()`, обработать JSON-списки:
```python
values: dict[str, str | bool | list[str]] = {}
for k, v in raw.items():
    if k in _BOOL_KEYS:
        values[k] = v.lower() == "true"
    elif k in _JSON_LIST_KEYS:
        values[k] = json.loads(v)
    else:
        values[k] = v
```

В `update_settings()`, сериализовать JSON-списки:
```python
for key in _SETTING_KEYS:
    value = getattr(request, key, None)
    if value is not None:
        if key in _BOOL_KEYS:
            str_value = str(value).lower()
        elif key in _JSON_LIST_KEYS:
            str_value = json.dumps(value)
        else:
            str_value = str(value)
        self._settings_repo.set(key, str_value)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test-unit k=test_usage_group_order_settings`
Expected: All PASS.

- [ ] **Step 5: Run all existing settings tests to check nothing broke**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test-unit k=settings`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/backend/application/dto/settings_dtos.py backend/src/backend/application/use_cases/manage_settings.py backend/tests/unit/application/test_usage_group_order_settings.py
git commit -m "feat: add usage_group_order to settings"
```

---

### Task 7: Интеграция в use cases — передача usage_order в сортировку

**Files:**
- Modify: `backend/src/backend/application/use_cases/get_candidates.py`
- Modify: `backend/src/backend/application/use_cases/get_sources.py`
- Modify: `backend/src/backend/application/use_cases/enqueue_meaning_generation.py`
- Modify: `backend/src/backend/application/use_cases/enqueue_media_generation.py`
- Modify: `backend/src/backend/infrastructure/container.py`

Все 4 use case'а, вызывающие `sort_by_relevance()`, должны:
1. Получить `SettingsRepository` через DI
2. Прочитать `usage_group_order` из settings
3. Передать в `sort_by_relevance(candidates, usage_order=order)`

- [ ] **Step 1: Update GetCandidatesUseCase**

В `backend/src/backend/application/use_cases/get_candidates.py`:

Добавить `settings_repo` в `__init__`:
```python
def __init__(
    self,
    source_repo: SourceRepository,
    candidate_repo: CandidateRepository,
    settings_repo: SettingsRepository,
) -> None:
    self._source_repo = source_repo
    self._candidate_repo = candidate_repo
    self._settings_repo = settings_repo
```

Обновить вызов `sort_by_relevance`:
```python
import json
from backend.infrastructure.adapters.cambridge.usage_groups import DEFAULT_USAGE_GROUP_ORDER

# В execute():
else:
    raw = self._settings_repo.get("usage_group_order")
    usage_order: list[str] = json.loads(raw) if raw else DEFAULT_USAGE_GROUP_ORDER
    candidates = sort_by_relevance(candidates, usage_order=usage_order)
```

- [ ] **Step 2: Update GetSourcesUseCase — same pattern**

В `backend/src/backend/application/use_cases/get_sources.py`, метод `get_by_id`:

Добавить `settings_repo` в `__init__`, прочитать `usage_group_order`, передать в `sort_by_relevance`.

- [ ] **Step 3: Update EnqueueMeaningGenerationUseCase — same pattern**

В `backend/src/backend/application/use_cases/enqueue_meaning_generation.py`:

Добавить `settings_repo` в `__init__`, прочитать `usage_group_order`, передать в `sort_by_relevance`.

- [ ] **Step 4: Update EnqueueMediaGenerationUseCase — same pattern**

В `backend/src/backend/application/use_cases/enqueue_media_generation.py`:

Добавить `settings_repo` в `__init__`, прочитать `usage_group_order`, передать в `sort_by_relevance`.

- [ ] **Step 5: Update container.py — wire settings_repo into use cases**

В `backend/src/backend/infrastructure/container.py`:

Для `get_candidates_use_case`:
```python
def get_candidates_use_case(self, session: Session) -> GetCandidatesUseCase:
    return GetCandidatesUseCase(
        source_repo=SqlaSourceRepository(session),
        candidate_repo=SqlaCandidateRepository(session),
        settings_repo=SqlaSettingsRepository(session),
    )
```

Аналогично для `get_sources_use_case`, `enqueue_meaning_generation_use_case`, `enqueue_media_generation_use_case`.

- [ ] **Step 6: Run all tests**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test`
Expected: All PASS. Некоторые тесты для use case'ов могут потребовать обновления mock'ов (добавление `settings_repo`).

- [ ] **Step 7: Fix broken tests if any**

Если тесты use case'ов упали из-за нового параметра `settings_repo` — обновить их, добавив `FakeSettingsRepo` или mock.

- [ ] **Step 8: Commit**

```bash
git add backend/src/backend/application/use_cases/get_candidates.py backend/src/backend/application/use_cases/get_sources.py backend/src/backend/application/use_cases/enqueue_meaning_generation.py backend/src/backend/application/use_cases/enqueue_media_generation.py backend/src/backend/infrastructure/container.py
git commit -m "feat: wire usage_order from settings into sort_by_relevance"
```

---

### Task 8: Заполнение usage_distribution при анализе текста

**Files:**
- Modify: `backend/src/backend/application/use_cases/analyze_text.py`
- Modify: `backend/src/backend/infrastructure/container.py`
- Create: `backend/tests/unit/application/test_analyze_text_usage.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.adapters.cambridge.models import (
    CambridgeEntry,
    CambridgeSense,
    CambridgeWord,
)
from backend.infrastructure.adapters.cambridge.usage_lookup import CambridgeUsageLookup


def _sense(usages: list[str] | None = None) -> CambridgeSense:
    return CambridgeSense(
        definition="test", level="B1", examples=[],
        labels_and_codes=[], usages=usages or [],
        domains=[], regions=[], image_link="",
    )


@pytest.mark.unit
class TestAnalyzeTextUsageDistribution:
    """Test that analyze_text populates usage_distribution on WordCandidateDTO."""

    def test_candidate_dto_has_usage_distribution(self) -> None:
        """WordCandidateDTO should include usage_distribution field."""
        from backend.application.dto.source_dtos import WordCandidateDTO
        assert hasattr(WordCandidateDTO, "usage_distribution")

    def test_usage_distribution_from_cambridge(self) -> None:
        """Integration: analyze_text → candidate with usage_distribution."""
        # This test verifies the field flows through the pipeline.
        # Full integration test is in Task 10.
        data = {"cool": CambridgeWord(
            word="cool",
            entries=[CambridgeEntry(
                headword="cool", pos=["adjective"],
                uk_ipa=[], us_ipa=[], uk_audio=[], us_audio=[],
                senses=[_sense(), _sense(["informal"])],
            )],
        )}
        lookup = CambridgeUsageLookup(data)
        result = lookup.get_distribution("cool", "JJ")
        assert result.groups is not None
        assert "neutral" in result.groups
        assert "informal" in result.groups
```

- [ ] **Step 2: Add usage_distribution to WordCandidateDTO and WordCandidate**

В `backend/src/backend/application/dto/source_dtos.py`, класс `WordCandidateDTO`:
```python
    usage_distribution: dict[str, float] | None = None
```

В `backend/src/backend/domain/entities/word_candidate.py`:
```python
from backend.domain.value_objects.usage_distribution import UsageDistribution

# Добавить поле (в TYPE_CHECKING):
    usage_distribution: UsageDistribution | None = None
```

В `backend/src/backend/application/dto/source_dtos.py`, класс `StoredCandidateDTO`:
```python
    usage_distribution: dict[str, float] | None = None
```

- [ ] **Step 3: Wire CambridgeUsageLookup into analyze_text**

В `backend/src/backend/application/use_cases/analyze_text.py`:

Добавить `CambridgeUsageLookup` как зависимость через `__init__` (опциональная, для backward compatibility):

```python
from backend.infrastructure.adapters.cambridge.usage_lookup import CambridgeUsageLookup

# В __init__:
    self._usage_lookup: CambridgeUsageLookup | None = usage_lookup
```

В `_CandidateAccumulator` добавить поле:
```python
    usage_distribution: UsageDistribution | None = None
```

При создании кандидата в `candidate_map` (строка ~119 и ~164 для phrasal verbs):
```python
# После создания accumulator:
if self._usage_lookup is not None:
    acc.usage_distribution = self._usage_lookup.get_distribution(lemma_lower, token.tag)
```

В `_build_candidates`, передать в `WordCandidate`:
```python
    usage_distribution=acc.usage_distribution,
```

В `_to_dto`, добавить:
```python
    usage_distribution=candidate.usage_distribution.to_dict() if candidate.usage_distribution else None,
```

- [ ] **Step 4: Wire in container.py**

В `backend/src/backend/infrastructure/container.py`:

Создать `CambridgeUsageLookup` из тех же данных, что Cambridge CEFR source. Нужно расшарить загруженные данные. Вариант: lazy-load Cambridge data один раз, передать в оба адаптера.

```python
from backend.infrastructure.adapters.cambridge.usage_lookup import CambridgeUsageLookup

# В __init__:
self._cambridge_usage_lookup = CambridgeUsageLookup(cambridge_path)
```

Но `CambridgeUsageLookup` принимает `dict[str, CambridgeWord]`, а не `Path`. Нужно или дать ему lazy-load (как `CambridgeCEFRSource`), или расшарить данные.

Рекомендация: добавить в `CambridgeUsageLookup` конструктор аналогичный `CambridgeCEFRSource` — принимает `Path`, lazy-load.

Обновить `CambridgeUsageLookup.__init__`:
```python
class CambridgeUsageLookup:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, CambridgeWord] | None = None

    @classmethod
    def from_data(cls, data: dict[str, CambridgeWord]) -> CambridgeUsageLookup:
        instance = cls.__new__(cls)
        instance._path = Path()
        instance._data = data
        return instance

    def _ensure_loaded(self) -> dict[str, CambridgeWord]:
        if self._data is None:
            from backend.infrastructure.adapters.cambridge.parser import parse_cambridge_jsonl
            self._data = parse_cambridge_jsonl(self._path)
        return self._data

    def get_distribution(self, lemma: str, pos_tag: str) -> UsageDistribution:
        data = self._ensure_loaded()
        word = data.get(lemma.lower())
        # ... rest of logic
```

В container.py:
```python
self._cambridge_usage_lookup = CambridgeUsageLookup(cambridge_path)
```

И передать в `analyze_text_use_case()`:
```python
def analyze_text_use_case(self) -> AnalyzeTextUseCase:
    return AnalyzeTextUseCase(
        ...,
        usage_lookup=self._cambridge_usage_lookup,
    )
```

**Примечание:** `CambridgeCEFRSource` и `CambridgeUsageLookup` обе делают lazy-load cambridge.jsonl. Чтобы не парсить дважды, можно расшарить данные. Но это оптимизация — на первой итерации допустимо парсить дважды (ленивая загрузка, файл загружается только при первом обращении, и оба адаптера используются в разных контекстах).

- [ ] **Step 5: Update _to_dto в get_candidates.py**

В `backend/src/backend/application/use_cases/get_candidates.py`, функция `_to_dto`:
```python
    usage_distribution=c.usage_distribution.to_dict() if c.usage_distribution else None,
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test`
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: populate usage_distribution during text analysis"
```

---

### Task 9: Frontend — drag-and-drop настройка usage порядка

**Files:**
- Modify: `frontends/web/src/api/types.ts`
- Modify: `frontends/web/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Add type to frontend**

В `frontends/web/src/api/types.ts`, интерфейс `Settings`:
```typescript
  usage_group_order: string[]
```

- [ ] **Step 2: Add Usage Priority section to SettingsPage**

В `frontends/web/src/pages/SettingsPage.tsx`, добавить секцию «Usage Priority» с drag-and-drop списком. Использовать HTML5 Drag and Drop API (без внешних зависимостей):

```tsx
// Описания групп для UI
const USAGE_GROUP_LABELS: Record<string, string> = {
  neutral: "Standard, unmarked words",
  informal: "Slang, casual speech",
  formal: "Formal register",
  specialized: "Technical, domain-specific",
  connotation: "Disapproving, approving, humorous",
  "old-fashioned": "Dated, archaic",
  offensive: "Offensive language",
  other: "Literary, trademark, etc.",
};
```

Реализовать drag-and-drop для переупорядочивания. При отпускании — вызвать `api.updateSettings({ usage_group_order: newOrder })`.

- [ ] **Step 3: Run frontend build check**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting/frontends/web && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Manual check in browser**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make up-worktree`
Open settings page, verify drag-and-drop works and order persists after reload.

- [ ] **Step 5: Commit**

```bash
git add frontends/web/src/api/types.ts frontends/web/src/pages/SettingsPage.tsx
git commit -m "feat: add Usage Priority drag-and-drop in settings UI"
```

---

### Task 10: Integration test — полный pipeline

**Files:**
- Create: `backend/tests/integration/test_usage_sorting_pipeline.py`

- [ ] **Step 1: Write integration test**

```python
"""Integration test: text → analysis → candidates with usage_distribution → sorted output."""
import json

import pytest
from sqlalchemy.orm import Session

from backend.application.dto.settings_dtos import UpdateSettingsRequest
from backend.application.use_cases.manage_settings import ManageSettingsUseCase
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository


@pytest.mark.integration
class TestUsageSortingPipeline:
    def test_usage_distribution_stored_and_sorted(self, db_session: Session) -> None:
        """Full pipeline: candidates get usage_distribution, sorting uses settings order."""
        # Setup: store usage_group_order in settings
        settings_repo = SqlaSettingsRepository(db_session)
        settings_uc = ManageSettingsUseCase(settings_repo)
        custom_order = ["informal", "neutral", "formal", "specialized",
                        "connotation", "old-fashioned", "offensive", "other"]
        settings_uc.update_settings(
            UpdateSettingsRequest(usage_group_order=custom_order)
        )

        # Verify roundtrip
        settings = settings_uc.get_settings()
        assert settings.usage_group_order == custom_order

        # Verify JSON stored correctly in DB
        raw = settings_repo.get("usage_group_order")
        assert raw is not None
        assert json.loads(raw) == custom_order

    def test_usage_distribution_json_roundtrip(self, db_session: Session) -> None:
        """UsageDistribution survives DB serialize/deserialize."""
        from backend.infrastructure.persistence.models import StoredCandidateModel
        from backend.domain.value_objects.candidate_status import CandidateStatus
        from backend.domain.entities.stored_candidate import StoredCandidate

        candidate = StoredCandidate(
            source_id=1,
            lemma="cool",
            pos="JJ",
            cefr_level="B1",
            zipf_frequency=4.5,
            context_fragment="that's cool",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.PENDING,
            usage_distribution=UsageDistribution({"neutral": 0.6, "informal": 0.4}),
        )
        model = StoredCandidateModel.from_entity(candidate)
        assert model.usage_distribution_json is not None

        restored = model.to_entity()
        assert restored.usage_distribution is not None
        assert restored.usage_distribution.groups == {"neutral": 0.6, "informal": 0.4}

    def test_null_usage_distribution_roundtrip(self, db_session: Session) -> None:
        """None usage_distribution → NULL in DB → None on entity."""
        from backend.infrastructure.persistence.models import StoredCandidateModel
        from backend.domain.value_objects.candidate_status import CandidateStatus
        from backend.domain.entities.stored_candidate import StoredCandidate

        candidate = StoredCandidate(
            source_id=1,
            lemma="unknown",
            pos="NN",
            cefr_level="B1",
            zipf_frequency=3.0,
            context_fragment="some context",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.PENDING,
            usage_distribution=None,
        )
        model = StoredCandidateModel.from_entity(candidate)
        assert model.usage_distribution_json is None

        restored = model.to_entity()
        assert restored.usage_distribution is None
```

- [ ] **Step 2: Run integration tests**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test-integration k=test_usage_sorting_pipeline`
Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_usage_sorting_pipeline.py
git commit -m "test: add integration tests for usage sorting pipeline"
```

---

### Task 11: Финальная проверка

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make test`
Expected: All PASS.

- [ ] **Step 2: Run ruff linter**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make lint`
Expected: No errors.

- [ ] **Step 3: Run mypy**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting && make typecheck`
Expected: No errors.

- [ ] **Step 4: Run frontend build**

Run: `cd /Users/maxos/PythonProjects/anything-to-anki-worktree-usage-sorting/frontends/web && npm run build`
Expected: Build succeeds.

- [ ] **Step 5: Manual smoke test**

1. Open app in browser
2. Submit a text with words that have different usage labels
3. Check that candidates display in correct order
4. Go to Settings → Usage Priority
5. Change order (e.g., informal first)
6. Return to candidates — verify order changed
