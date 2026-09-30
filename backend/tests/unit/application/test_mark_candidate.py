from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.mark_candidate import MarkCandidateUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus


@pytest.mark.unit
class TestMarkCandidateUseCase:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.known_word_repo = MagicMock()
        self.review_status = MagicMock()
        self.use_case = MarkCandidateUseCase(
            candidate_repo=self.candidate_repo,
            known_word_repo=self.known_word_repo,
            review_status=self.review_status,
        )

    def test_mark_as_learn(self) -> None:
        self.candidate_repo.get_by_id.return_value = StoredCandidate(
            id=1, source_id=1, lemma="pursuit", pos="NOUN",
            cefr_level="B2", zipf_frequency=3.5,
            context_fragment="the pursuit of", fragment_purity="clean",
            occurrences=1, status=CandidateStatus.PENDING,
        )
        self.use_case.execute(1, CandidateStatus.LEARN)
        self.candidate_repo.update_status.assert_called_once_with(1, CandidateStatus.LEARN)
        self.known_word_repo.add.assert_not_called()

    def test_mark_as_known_adds_to_whitelist(self) -> None:
        self.candidate_repo.get_by_id.return_value = StoredCandidate(
            id=1, source_id=1, lemma="pursuit", pos="NOUN",
            cefr_level="B2", zipf_frequency=3.5,
            context_fragment="the pursuit of", fragment_purity="clean",
            occurrences=1, status=CandidateStatus.PENDING,
        )
        self.use_case.execute(1, CandidateStatus.KNOWN)
        self.candidate_repo.update_status.assert_called_once_with(1, CandidateStatus.KNOWN)
        self.known_word_repo.add.assert_called_once_with("pursuit", "NOUN")

    def test_refreshes_the_source_review_status(self) -> None:
        self.candidate_repo.get_by_id.return_value = StoredCandidate(
            id=1, source_id=5, lemma="pursuit", pos="NOUN",
            cefr_level="B2", zipf_frequency=3.5,
            context_fragment="the pursuit of", fragment_purity="clean",
            occurrences=1, status=CandidateStatus.PENDING,
        )
        self.use_case.execute(1, CandidateStatus.SKIP)
        self.review_status.refresh.assert_called_once_with(5)

    def _existing(self, status: CandidateStatus) -> None:
        self.candidate_repo.get_by_id.return_value = StoredCandidate(
            id=1, source_id=5, lemma="pursuit", pos="NOUN",
            cefr_level="B2", zipf_frequency=3.5,
            context_fragment="the pursuit of", fragment_purity="clean",
            occurrences=1, status=status,
        )

    def test_undo_returns_the_candidate_to_pending(self) -> None:
        self._existing(CandidateStatus.LEARN)
        self.use_case.execute(1, CandidateStatus.PENDING)
        self.candidate_repo.update_status.assert_called_once_with(1, CandidateStatus.PENDING)
        self.review_status.refresh.assert_called_once_with(5)

    def test_leaving_known_takes_the_word_off_the_whitelist(self) -> None:
        self._existing(CandidateStatus.KNOWN)
        self.use_case.execute(1, CandidateStatus.PENDING)
        self.known_word_repo.remove_by_lemma.assert_called_once_with("pursuit", "NOUN")

    def test_staying_known_keeps_the_word(self) -> None:
        self._existing(CandidateStatus.KNOWN)
        self.use_case.execute(1, CandidateStatus.KNOWN)
        self.known_word_repo.remove_by_lemma.assert_not_called()

    def test_not_found(self) -> None:
        self.candidate_repo.get_by_id.return_value = None
        with pytest.raises(CandidateNotFoundError):
            self.use_case.execute(999, CandidateStatus.LEARN)
