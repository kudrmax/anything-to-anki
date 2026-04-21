from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_reprocess_stats import (
    GetReprocessStatsUseCase,
    ReprocessStats,
)
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus


def _make_use_case() -> tuple[GetReprocessStatsUseCase, dict[str, MagicMock]]:
    mocks: dict[str, MagicMock] = {
        "source_repo": MagicMock(),
        "candidate_repo": MagicMock(),
        "known_word_repo": MagicMock(),
        "meaning_repo": MagicMock(),
        "media_repo": MagicMock(),
        "pronunciation_repo": MagicMock(),
    }
    use_case = GetReprocessStatsUseCase(
        source_repo=mocks["source_repo"],
        candidate_repo=mocks["candidate_repo"],
        known_word_repo=mocks["known_word_repo"],
        meaning_repo=mocks["meaning_repo"],
        media_repo=mocks["media_repo"],
        pronunciation_repo=mocks["pronunciation_repo"],
    )
    return use_case, mocks


def _make_candidate(
    source_id: int,
    status: CandidateStatus,
    lemma: str = "test",
    pos: str = "NOUN",
) -> StoredCandidate:
    return StoredCandidate(
        source_id=source_id,
        lemma=lemma,
        pos=pos,
        cefr_level="B2",
        zipf_frequency=3.5,
        context_fragment="a test fragment",
        fragment_purity="clean",
        occurrences=1,
        status=status,
    )


def _no_active_jobs(mocks: dict[str, MagicMock]) -> None:
    for repo_name in ("meaning_repo", "media_repo", "pronunciation_repo"):
        mocks[repo_name].get_candidate_ids_by_status.return_value = []


@pytest.mark.unit
class TestGetReprocessStatsUseCase:
    def test_returns_counts(self) -> None:
        use_case, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = MagicMock()
        mocks["candidate_repo"].get_by_source.return_value = [
            _make_candidate(1, CandidateStatus.LEARN, lemma="new_word"),
            _make_candidate(1, CandidateStatus.KNOWN, lemma="word_a"),
            _make_candidate(1, CandidateStatus.SKIP),
            _make_candidate(1, CandidateStatus.PENDING),
        ]
        # neither new_word nor word_a in known_words — both will be lost
        mocks["known_word_repo"].get_all_pairs.return_value = set()
        _no_active_jobs(mocks)

        result = use_case.execute(1)

        assert result.learn_count == 1  # not in whitelist → lost
        assert result.known_count == 1  # not in whitelist → lost
        assert result.skip_count == 1
        assert result.pending_count == 1
        assert result.has_active_jobs is False

    def test_learn_not_in_whitelist_counted_as_lost(self) -> None:
        use_case, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = MagicMock()
        mocks["candidate_repo"].get_by_source.return_value = [
            _make_candidate(1, CandidateStatus.LEARN, lemma="unsaved", pos="VERB"),
            _make_candidate(1, CandidateStatus.LEARN, lemma="also_unsaved", pos="NOUN"),
        ]
        mocks["known_word_repo"].get_all_pairs.return_value = set()
        _no_active_jobs(mocks)

        result = use_case.execute(1)

        assert result.learn_count == 2

    def test_learn_in_whitelist_not_counted_as_lost(self) -> None:
        use_case, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = MagicMock()
        mocks["candidate_repo"].get_by_source.return_value = [
            _make_candidate(1, CandidateStatus.LEARN, lemma="exported", pos="VERB"),
            _make_candidate(1, CandidateStatus.LEARN, lemma="not_exported", pos="VERB"),
        ]
        # "exported" already in known_words (was synced to Anki)
        mocks["known_word_repo"].get_all_pairs.return_value = {("exported", "VERB")}
        _no_active_jobs(mocks)

        result = use_case.execute(1)

        assert result.learn_count == 1  # only "not_exported" is at risk

    def test_all_learn_in_whitelist_zero_lost(self) -> None:
        use_case, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = MagicMock()
        mocks["candidate_repo"].get_by_source.return_value = [
            _make_candidate(1, CandidateStatus.LEARN, lemma="word_a", pos="NOUN"),
            _make_candidate(1, CandidateStatus.LEARN, lemma="word_b", pos="ADJ"),
        ]
        mocks["known_word_repo"].get_all_pairs.return_value = {
            ("word_a", "NOUN"),
            ("word_b", "ADJ"),
        }
        _no_active_jobs(mocks)

        result = use_case.execute(1)

        assert result.learn_count == 0

    def test_known_in_whitelist_not_counted_as_lost(self) -> None:
        use_case, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = MagicMock()
        mocks["candidate_repo"].get_by_source.return_value = [
            _make_candidate(1, CandidateStatus.KNOWN, lemma="safe", pos="ADJ"),
            _make_candidate(1, CandidateStatus.KNOWN, lemma="unsafe", pos="ADJ"),
        ]
        # only "safe" is in known_words
        mocks["known_word_repo"].get_all_pairs.return_value = {("safe", "ADJ")}
        _no_active_jobs(mocks)

        result = use_case.execute(1)

        assert result.known_count == 1  # only "unsafe" is lost

    def test_all_known_in_whitelist_zero_lost(self) -> None:
        use_case, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = MagicMock()
        mocks["candidate_repo"].get_by_source.return_value = [
            _make_candidate(1, CandidateStatus.KNOWN, lemma="word", pos="NOUN"),
        ]
        mocks["known_word_repo"].get_all_pairs.return_value = {("word", "NOUN")}
        _no_active_jobs(mocks)

        result = use_case.execute(1)

        assert result.known_count == 0

    def test_has_active_jobs_when_meaning_running(self) -> None:
        use_case, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = MagicMock()
        mocks["candidate_repo"].get_by_source.return_value = []
        mocks["known_word_repo"].get_all_pairs.return_value = set()

        def meaning_ids_by_status(source_id: int, status: EnrichmentStatus) -> list[int]:
            if status == EnrichmentStatus.RUNNING:
                return [10]
            return []

        mocks["meaning_repo"].get_candidate_ids_by_status.side_effect = meaning_ids_by_status
        mocks["media_repo"].get_candidate_ids_by_status.return_value = []
        mocks["pronunciation_repo"].get_candidate_ids_by_status.return_value = []

        result = use_case.execute(1)

        assert result.has_active_jobs is True

    def test_not_found(self) -> None:
        use_case, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = None

        with pytest.raises(SourceNotFoundError):
            use_case.execute(999)
