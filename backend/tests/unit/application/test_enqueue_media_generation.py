"""Unit tests for EnqueueMediaGenerationUseCase.

Mirrors test_enqueue_meaning_generation: covers RELEVANCE branch (just
delegates to repo with sort_order kwarg) and CHRONOLOGICAL branch (re-sorts
in Python by text position). Marking eligible ids as QUEUED is the side
effect that the worker depends on.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.application.use_cases.enqueue_media_generation import (
    EnqueueMediaGenerationUseCase,
)
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus


def _make_source(
    *, raw: str = "foo bar", cleaned: str | None = None
) -> Source:
    return Source(
        id=1, raw_text=raw, cleaned_text=cleaned, status=SourceStatus.DONE,
        input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
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
    media_repo: MagicMock,
    candidate_repo: MagicMock | None = None,
    source_repo: MagicMock | None = None,
) -> EnqueueMediaGenerationUseCase:
    return EnqueueMediaGenerationUseCase(
        media_repo=media_repo,
        candidate_repo=candidate_repo or MagicMock(),
        source_repo=source_repo or MagicMock(),
    )


# --- RELEVANCE branch -----------------------------------------------------


@pytest.mark.unit
class TestRelevanceBranch:
    def test_returns_eligible_ids_and_marks_queued(self) -> None:
        media_repo = MagicMock()
        media_repo.get_eligible_candidate_ids.return_value = [10, 20, 30]
        use_case = _make_use_case(media_repo)

        result = use_case.execute(
            source_id=1, sort_order=CandidateSortOrder.RELEVANCE
        )

        assert result == [10, 20, 30]
        media_repo.get_eligible_candidate_ids.assert_called_once_with(
            source_id=1, sort_order=CandidateSortOrder.RELEVANCE
        )
        media_repo.mark_queued_bulk.assert_called_once_with([10, 20, 30])

    def test_empty_returns_empty_and_does_not_mark_queued(self) -> None:
        media_repo = MagicMock()
        media_repo.get_eligible_candidate_ids.return_value = []
        use_case = _make_use_case(media_repo)

        result = use_case.execute(
            source_id=1, sort_order=CandidateSortOrder.RELEVANCE
        )
        assert result == []
        media_repo.mark_queued_bulk.assert_not_called()

    def test_default_sort_order_is_none_uses_relevance_branch(self) -> None:
        media_repo = MagicMock()
        media_repo.get_eligible_candidate_ids.return_value = [5]
        use_case = _make_use_case(media_repo)

        result = use_case.execute(source_id=1)
        assert result == [5]
        kwargs = media_repo.get_eligible_candidate_ids.call_args.kwargs
        assert kwargs["sort_order"] is None


# --- CHRONOLOGICAL branch -------------------------------------------------


@pytest.mark.unit
class TestChronologicalBranch:
    def test_re_sorts_by_text_position(self) -> None:
        media_repo = MagicMock()
        media_repo.get_eligible_candidate_ids.return_value = [3, 1, 2]
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
        use_case = _make_use_case(media_repo, candidate_repo, source_repo)

        result = use_case.execute(
            source_id=1, sort_order=CandidateSortOrder.CHRONOLOGICAL
        )

        assert result == [3, 1, 2]
        media_repo.mark_queued_bulk.assert_called_once_with([3, 1, 2])
        # In CHRONOLOGICAL branch, the repo is called WITHOUT sort_order kwarg.
        media_repo.get_eligible_candidate_ids.assert_called_once_with(source_id=1)

    def test_empty_skips_lookups(self) -> None:
        media_repo = MagicMock()
        media_repo.get_eligible_candidate_ids.return_value = []
        candidate_repo = MagicMock()
        source_repo = MagicMock()
        use_case = _make_use_case(media_repo, candidate_repo, source_repo)

        result = use_case.execute(
            source_id=1, sort_order=CandidateSortOrder.CHRONOLOGICAL
        )

        assert result == []
        candidate_repo.get_by_ids.assert_not_called()
        source_repo.get_by_id.assert_not_called()
        media_repo.mark_queued_bulk.assert_not_called()

    def test_source_not_found_returns_empty(self) -> None:
        media_repo = MagicMock()
        media_repo.get_eligible_candidate_ids.return_value = [1, 2]
        candidate_repo = MagicMock()
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = None
        use_case = _make_use_case(media_repo, candidate_repo, source_repo)

        result = use_case.execute(
            source_id=999, sort_order=CandidateSortOrder.CHRONOLOGICAL
        )

        assert result == []
        media_repo.mark_queued_bulk.assert_not_called()
        candidate_repo.get_by_ids.assert_not_called()

    def test_uses_raw_text_when_cleaned_text_is_none(self) -> None:
        media_repo = MagicMock()
        media_repo.get_eligible_candidate_ids.return_value = [1, 2]
        candidate_repo = MagicMock()
        candidate_repo.get_by_ids.return_value = [
            _make_candidate(id_=1, fragment="zebra"),
            _make_candidate(id_=2, fragment="apple"),
        ]
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _make_source(
            raw="apple zebra", cleaned=None
        )
        use_case = _make_use_case(media_repo, candidate_repo, source_repo)

        result = use_case.execute(
            source_id=1, sort_order=CandidateSortOrder.CHRONOLOGICAL
        )
        assert result == [2, 1]

    def test_prefers_cleaned_text_over_raw(self) -> None:
        media_repo = MagicMock()
        media_repo.get_eligible_candidate_ids.return_value = [1, 2]
        candidate_repo = MagicMock()
        candidate_repo.get_by_ids.return_value = [
            _make_candidate(id_=1, fragment="zebra"),
            _make_candidate(id_=2, fragment="apple"),
        ]
        source_repo = MagicMock()
        source_repo.get_by_id.return_value = _make_source(
            raw="zebra apple", cleaned="apple zebra"
        )
        use_case = _make_use_case(media_repo, candidate_repo, source_repo)

        result = use_case.execute(
            source_id=1, sort_order=CandidateSortOrder.CHRONOLOGICAL
        )
        assert result == [2, 1]
