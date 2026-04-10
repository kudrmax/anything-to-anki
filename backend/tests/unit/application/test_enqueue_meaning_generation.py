"""Unit tests for EnqueueMeaningGenerationUseCase.

The use case is critical for queue correctness:
- It marks all eligible candidates as QUEUED in one atomic call.
- It splits ids into batches of 15 (the worker batch size).
- For CHRONOLOGICAL sort it has to re-sort by text position because the
  meaning repo only knows RELEVANCE / id-asc.

These tests cover both branches.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.application.use_cases.enqueue_meaning_generation import (
    BATCH_SIZE,
    EnqueueMeaningGenerationUseCase,
)
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.source_status import SourceStatus


def _make_source(
    *,
    id_: int = 1,
    raw: str = "foo bar baz",
    cleaned: str | None = None,
) -> Source:
    return Source(
        id=id_,
        raw_text=raw,
        cleaned_text=cleaned,
        status=SourceStatus.DONE,
    )


def _make_candidate(*, id_: int, fragment: str) -> StoredCandidate:
    return StoredCandidate(
        id=id_,
        source_id=1,
        lemma="x",
        pos="NOUN",
        cefr_level=None,
        zipf_frequency=5.0,
        is_sweet_spot=False,
        context_fragment=fragment,
        fragment_purity="clean",
        occurrences=1,
        surface_form=None,
        is_phrasal_verb=False,
        status=CandidateStatus.PENDING,
    )


def _make_use_case(
    meaning_repo: MagicMock,
    candidate_repo: MagicMock | None = None,
    source_repo: MagicMock | None = None,
) -> EnqueueMeaningGenerationUseCase:
    return EnqueueMeaningGenerationUseCase(
        meaning_repo=meaning_repo,
        candidate_repo=candidate_repo or MagicMock(),
        source_repo=source_repo or MagicMock(),
    )


# --- RELEVANCE branch (default) -------------------------------------------


@pytest.mark.unit
class TestRelevanceBranch:
    def test_returns_batches_of_15_and_marks_queued(self) -> None:
        ids = list(range(1, 33))  # 32 ids
        meaning_repo = MagicMock()
        meaning_repo.get_candidate_ids_without_meaning.return_value = ids
        use_case = _make_use_case(meaning_repo)

        result = use_case.execute(source_id=1, sort_order=CandidateSortOrder.RELEVANCE)

        assert len(result) == 3
        assert result[0] == list(range(1, 16))
        assert result[1] == list(range(16, 31))
        assert result[2] == list(range(31, 33))
        assert sum(len(b) for b in result) == 32
        meaning_repo.get_candidate_ids_without_meaning.assert_called_once_with(
            source_id=1,
            only_active=True,
            sort_order=CandidateSortOrder.RELEVANCE,
        )
        meaning_repo.mark_queued_bulk.assert_called_once_with(ids)

    def test_empty_returns_empty_and_does_not_mark_queued(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_candidate_ids_without_meaning.return_value = []
        use_case = _make_use_case(meaning_repo)

        result = use_case.execute(source_id=1, sort_order=CandidateSortOrder.RELEVANCE)

        assert result == []
        meaning_repo.mark_queued_bulk.assert_not_called()

    def test_default_sort_order_is_none_treated_as_relevance(self) -> None:
        """When sort_order is None, the use case takes the RELEVANCE-branch
        (the ``else`` of the chronological check)."""
        meaning_repo = MagicMock()
        meaning_repo.get_candidate_ids_without_meaning.return_value = [10, 20]
        use_case = _make_use_case(meaning_repo)

        result = use_case.execute(source_id=1)

        assert result == [[10, 20]]
        # The repo call must NOT have set sort_order kwarg to a value other than None.
        kwargs = meaning_repo.get_candidate_ids_without_meaning.call_args.kwargs
        assert kwargs["sort_order"] is None

    def test_batch_size_constant_is_15(self) -> None:
        # If somebody changes BATCH_SIZE, the worker contract changes — guard it.
        assert BATCH_SIZE == 15


# --- CHRONOLOGICAL branch -------------------------------------------------


@pytest.mark.unit
class TestChronologicalBranch:
    def test_re_sorts_candidates_by_text_position(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_candidate_ids_without_meaning.return_value = [3, 1, 2]
        candidate_repo = MagicMock()
        candidate_repo.get_by_ids.return_value = [
            _make_candidate(id_=1, fragment="baz"),
            _make_candidate(id_=2, fragment="qux"),
            _make_candidate(id_=3, fragment="foo"),
        ]
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _make_source(
            raw="foo bar baz qux"
        )
        use_case = _make_use_case(meaning_repo, candidate_repo, source_repo)

        result = use_case.execute(
            source_id=1, sort_order=CandidateSortOrder.CHRONOLOGICAL
        )

        # Order by find: foo@0 < baz@8 < qux@12 → ids [3, 1, 2]
        assert result == [[3, 1, 2]]
        meaning_repo.mark_queued_bulk.assert_called_once_with([3, 1, 2])
        # Repo was called WITHOUT sort_order kwarg in CHRONOLOGICAL branch.
        meaning_repo.get_candidate_ids_without_meaning.assert_called_once_with(
            source_id=1, only_active=True
        )

    def test_empty_skips_source_and_candidate_lookup(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_candidate_ids_without_meaning.return_value = []
        candidate_repo = MagicMock()
        source_repo = MagicMock()
        use_case = _make_use_case(meaning_repo, candidate_repo, source_repo)

        result = use_case.execute(
            source_id=1, sort_order=CandidateSortOrder.CHRONOLOGICAL
        )

        assert result == []
        candidate_repo.get_by_ids.assert_not_called()
        source_repo.get_by_id.assert_not_called()
        meaning_repo.mark_queued_bulk.assert_not_called()

    def test_source_not_found_returns_empty(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_candidate_ids_without_meaning.return_value = [1, 2]
        candidate_repo = MagicMock()
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = None
        use_case = _make_use_case(meaning_repo, candidate_repo, source_repo)

        result = use_case.execute(
            source_id=999, sort_order=CandidateSortOrder.CHRONOLOGICAL
        )

        assert result == []
        meaning_repo.mark_queued_bulk.assert_not_called()
        candidate_repo.get_by_ids.assert_not_called()

    def test_uses_raw_text_when_cleaned_text_is_none(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_candidate_ids_without_meaning.return_value = [1, 2]
        candidate_repo = MagicMock()
        candidate_repo.get_by_ids.return_value = [
            _make_candidate(id_=1, fragment="zebra"),
            _make_candidate(id_=2, fragment="apple"),
        ]
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _make_source(
            raw="apple zebra", cleaned=None
        )
        use_case = _make_use_case(meaning_repo, candidate_repo, source_repo)

        result = use_case.execute(
            source_id=1, sort_order=CandidateSortOrder.CHRONOLOGICAL
        )

        # apple is at 0, zebra at 6 → [2, 1]
        assert result == [[2, 1]]

    def test_prefers_cleaned_text_over_raw_text(self) -> None:
        """If cleaned_text is set, the use case must sort by it (not raw)."""
        meaning_repo = MagicMock()
        meaning_repo.get_candidate_ids_without_meaning.return_value = [1, 2]
        candidate_repo = MagicMock()
        candidate_repo.get_by_ids.return_value = [
            _make_candidate(id_=1, fragment="zebra"),
            _make_candidate(id_=2, fragment="apple"),
        ]
        source_repo = MagicMock()
        # raw says zebra-first, cleaned says apple-first; cleaned must win.
        source_repo.get_by_id.return_value = _make_source(
            raw="zebra apple", cleaned="apple zebra"
        )
        use_case = _make_use_case(meaning_repo, candidate_repo, source_repo)

        result = use_case.execute(
            source_id=1, sort_order=CandidateSortOrder.CHRONOLOGICAL
        )
        assert result == [[2, 1]]
